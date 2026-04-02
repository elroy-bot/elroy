from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

from sqlmodel import select

from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import Memory
from ...repository.documents.operations import do_ingest, do_ingest_dir
from ...repository.memories.file_storage import read_memory_frontmatter, read_memory_text, write_id_to_frontmatter
from ...repository.user.operations import get_or_create_user_preference
from ...utils.clock import utc_now

logger = get_logger()


@dataclass(frozen=True)
class DocumentIngestionTarget:
    path: Path
    kind: str


class DocumentIngestionService:
    def __init__(self, ctx: ElroyContext):
        self.ctx = ctx

    def build_exclude_patterns(self) -> list[str]:
        if not self.ctx.memory_dir:
            return []
        memory_dir_resolved = Path(self.ctx.memory_dir).expanduser().resolve()
        return [str(memory_dir_resolved), str(memory_dir_resolved / "**")]

    def iter_targets(self) -> list[DocumentIngestionTarget]:
        targets: list[DocumentIngestionTarget] = []
        memory_dir_resolved = Path(self.ctx.memory_dir).expanduser().resolve() if self.ctx.memory_dir else None
        for path_str in self.ctx.background_ingest_paths:
            path = Path(path_str).expanduser().resolve()
            if not path.exists():
                logger.warning(f"Background ingest path does not exist: {path}")
                continue
            if memory_dir_resolved is not None:
                try:
                    path.relative_to(memory_dir_resolved)
                    logger.debug(f"Skipping memory_dir path from background ingestion: {path}")
                    continue
                except ValueError:
                    pass
            if path.is_file():
                targets.append(DocumentIngestionTarget(path=path, kind="file"))
            elif path.is_dir():
                targets.append(DocumentIngestionTarget(path=path, kind="directory"))
        return targets

    def ingest_target(self, target: DocumentIngestionTarget, exclude: list[str]) -> None:
        if target.kind == "file":
            result = do_ingest(self.ctx, target.path, force_refresh=False)
            logger.info(f"Background ingested {target.path}: {result.name}")
            return

        total_processed = 0
        for status_update in do_ingest_dir(
            self.ctx,
            target.path,
            force_refresh=False,
            recursive=True,
            include=[],
            exclude=exclude,
        ):
            total_processed = sum(status_update.statuses.values())
        logger.info(f"Background ingested directory {target.path}: {total_processed} files processed")

    def record_last_run(self, start_time) -> None:
        user_pref = get_or_create_user_preference(self.ctx)
        user_pref.background_ingest_last_run = start_time
        self.ctx.db.session.add(user_pref)
        self.ctx.db.session.commit()
        logger.debug(f"Recorded background ingestion last run time: {start_time}")

    def initial_delay_seconds(self) -> int:
        user_pref = get_or_create_user_preference(self.ctx)
        last_run = user_pref.background_ingest_last_run
        interval_minutes = self.ctx.background_ingest_interval_minutes
        now = utc_now()
        if last_run is None:
            logger.info("Background ingestion has never run - scheduling first run in 10 seconds")
            return 10
        next_run_time = last_run + timedelta(minutes=interval_minutes)
        time_until_next = (next_run_time - now).total_seconds()
        if time_until_next <= 0:
            logger.info(f"Background ingestion last ran {(now - last_run).total_seconds() / 60:.1f} minutes ago - scheduling immediate run")
            return 10
        logger.info(
            f"Background ingestion last ran {(now - last_run).total_seconds() / 60:.1f} minutes ago - "
            f"scheduling next run in {time_until_next / 60:.1f} minutes"
        )
        return int(time_until_next)


@dataclass(frozen=True)
class MemorySyncPlan:
    disk_files: list[Path]
    disk_id_to_path: dict[int, Path]
    disk_path_to_fm: dict[Path, dict[str, Any]]
    db_file_memories: list[Memory]


class MemoryFileSyncService:
    def __init__(self, ctx: ElroyContext):
        self.ctx = ctx

    def build_plan(self) -> MemorySyncPlan:
        disk_files = [p for p in self.ctx.memory_dir_path.glob("*.md") if p.is_file()]
        disk_id_to_path: dict[int, Path] = {}
        disk_path_to_fm: dict[Path, dict[str, Any]] = {}
        for path in disk_files:
            fm = read_memory_frontmatter(path)
            disk_path_to_fm[path] = fm
            if "id" not in fm:
                continue
            try:
                disk_id_to_path[int(fm["id"])] = path
            except (ValueError, TypeError):
                continue
        db_file_memories = list(
            self.ctx.db.exec(
                select(Memory).where(
                    Memory.user_id == self.ctx.user_id,
                    cast(Any, Memory.is_active),
                    Memory.file_path.is_not(None),  # type: ignore[union-attr]
                )
            ).all()
        )
        return MemorySyncPlan(
            disk_files=disk_files,
            disk_id_to_path=disk_id_to_path,
            disk_path_to_fm=disk_path_to_fm,
            db_file_memories=db_file_memories,
        )

    def apply_plan(self, plan: MemorySyncPlan) -> None:
        self._sync_new_disk_files(plan.disk_files, plan.disk_path_to_fm)
        db_id_to_memory: dict[int, Memory] = {m.id: m for m in plan.db_file_memories if m.id}
        self._sync_existing_disk_files(plan.disk_id_to_path, db_id_to_memory)
        self._mark_missing_disk_files(plan.db_file_memories)

    def _sync_new_disk_files(self, disk_files: list[Path], disk_path_to_fm: dict[Path, dict[str, Any]]) -> None:
        from ...repository.memories.operations import do_create_memory

        for path in disk_files:
            fm = disk_path_to_fm[path]
            if "id" in fm:
                continue
            text = read_memory_text(path)
            name = path.stem.replace("_", " ")
            try:
                memory = do_create_memory(self.ctx, name, text, [], False)
                assert memory.id is not None
                if memory.file_path and memory.file_path != str(path):
                    new_path = Path(memory.file_path)
                    if new_path.exists() and new_path != path:
                        new_path.unlink()
                    memory.file_path = str(path)
                    self.ctx.db.add(memory)
                    self.ctx.db.commit()
                write_id_to_frontmatter(path, memory.id)
                logger.info(f"Created new memory from file {path.name}: id={memory.id}")
            except Exception as e:
                logger.error(f"Failed to create memory from file {path}: {e}", exc_info=True)

    def _sync_existing_disk_files(self, disk_id_to_path: dict[int, Path], db_id_to_memory: dict[int, Memory]) -> None:
        from ...repository.recall.operations import upsert_embedding_if_needed

        for mid, disk_path in disk_id_to_path.items():
            db_memory = db_id_to_memory.get(mid)
            if db_memory is None:
                logger.warning(f"File {disk_path.name} has id={mid} but no active memory found in DB; ignoring")
                continue
            if db_memory.file_path != str(disk_path):
                old_name = db_memory.name
                db_memory.file_path = str(disk_path)
                db_memory.name = disk_path.stem.replace("_", " ")
                self.ctx.db.add(db_memory)
                self.ctx.db.commit()
                logger.info(f"Memory {mid} renamed: {old_name!r} -> {db_memory.name!r}, path updated")
            try:
                upsert_embedding_if_needed(self.ctx, db_memory)
            except Exception as e:
                logger.error(f"Failed to re-embed memory {mid} from file {disk_path}: {e}", exc_info=True)

    def _mark_missing_disk_files(self, db_file_memories: list[Memory]) -> None:
        from ...repository.memories.operations import mark_inactive

        for db_memory in db_file_memories:
            if not db_memory.file_path:
                continue
            db_path = Path(db_memory.file_path)
            if db_path.exists():
                continue
            logger.info(f"Memory file disappeared: {db_path.name}; marking memory {db_memory.id} inactive")
            db_memory.file_path = None
            self.ctx.db.add(db_memory)
            self.ctx.db.commit()
            try:
                mark_inactive(self.ctx, db_memory)
            except Exception as e:
                logger.error(f"Failed to mark memory {db_memory.id} inactive: {e}", exc_info=True)
