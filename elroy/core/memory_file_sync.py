from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sqlmodel import select

from ..db.db_models import Memory
from ..repository.memories.factory import build_memory_lifecycle_orchestrator
from ..repository.memories.file_storage import read_memory_frontmatter, read_memory_text, write_id_to_frontmatter
from ..repository.memories.runtime import build_memory_runtime
from ..repository.recall.factory import build_recall_indexer
from ..repository.user.session import build_user_session
from .logging import get_logger
from .turn import TurnContext

logger = get_logger()


@dataclass(frozen=True)
class MemorySyncPlan:
    disk_files: list[Path]
    disk_id_to_path: dict[int, Path]
    disk_path_to_fm: dict[Path, dict[str, Any]]
    db_file_memories: list[Memory]


class MemoryFileSyncOrchestrator:
    def __init__(self, turn: TurnContext):
        self.turn = turn
        self.runtime = build_memory_runtime(turn)
        self.user_session = build_user_session(turn)
        self.db = self.user_session.db
        self.memory_lifecycle_orchestrator = build_memory_lifecycle_orchestrator(turn)
        self.recall_indexer = build_recall_indexer(turn)

    def build_plan(self) -> MemorySyncPlan:
        user_id = self.user_session.user_id
        disk_files = [p for p in self.runtime.memory_dir_path.glob("*.md") if p.is_file()]
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
            self.db.exec(
                select(Memory).where(
                    Memory.user_id == user_id,
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
        for path in disk_files:
            fm = disk_path_to_fm[path]
            if "id" in fm:
                continue
            text = read_memory_text(path)
            name = path.stem.replace("_", " ")
            try:
                memory = self.memory_lifecycle_orchestrator.do_create_memory(name, text, [], False)
                assert memory.id is not None
                if memory.file_path and memory.file_path != str(path):
                    new_path = Path(memory.file_path)
                    if new_path.exists() and new_path != path:
                        new_path.unlink()
                    memory.file_path = str(path)
                    self.db.add(memory)
                    self.db.commit()
                write_id_to_frontmatter(path, memory.id)
                logger.info(f"Created new memory from file {path.name}: id={memory.id}")
            except Exception as e:
                logger.error(f"Failed to create memory from file {path}: {e}", exc_info=True)

    def _sync_existing_disk_files(self, disk_id_to_path: dict[int, Path], db_id_to_memory: dict[int, Memory]) -> None:
        for mid, disk_path in disk_id_to_path.items():
            db_memory = db_id_to_memory.get(mid)
            if db_memory is None:
                logger.warning(f"File {disk_path.name} has id={mid} but no active memory found in DB; ignoring")
                continue
            if db_memory.file_path != str(disk_path):
                old_name = db_memory.name
                db_memory.file_path = str(disk_path)
                db_memory.name = disk_path.stem.replace("_", " ")
                self.db.add(db_memory)
                self.db.commit()
                logger.info(f"Memory {mid} renamed: {old_name!r} -> {db_memory.name!r}, path updated")
            try:
                self.recall_indexer.upsert_embedding_if_needed(db_memory)
            except Exception as e:
                logger.error(f"Failed to re-embed memory {mid} from file {disk_path}: {e}", exc_info=True)

    def _mark_missing_disk_files(self, db_file_memories: list[Memory]) -> None:
        for db_memory in db_file_memories:
            if not db_memory.file_path:
                continue
            db_path = Path(db_memory.file_path)
            if db_path.exists():
                continue
            logger.info(f"Memory file disappeared: {db_path.name}; marking memory {db_memory.id} inactive")
            db_memory.file_path = None
            self.db.add(db_memory)
            self.db.commit()
            try:
                self.memory_lifecycle_orchestrator.mark_inactive(db_memory)
            except Exception as e:
                logger.error(f"Failed to mark memory {db_memory.id} inactive: {e}", exc_info=True)
