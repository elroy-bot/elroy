"""Background memory file sync for file-backed memories (Obsidian integration)."""

from pathlib import Path
from typing import Any, cast

from apscheduler.job import Job
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import select

from ...core.async_tasks import get_scheduler
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...core.status import clear_background_status, set_background_status
from ...db.db_models import Memory
from .file_storage import (
    read_memory_frontmatter,
    read_memory_text,
    write_id_to_frontmatter,
)

logger = get_logger()


def _index_disk_memory_files(disk_files: list[Path]) -> tuple[dict[int, Path], dict[Path, dict[str, Any]]]:
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
    return disk_id_to_path, disk_path_to_fm


def _load_db_file_memories(ctx: ElroyContext) -> list[Memory]:
    return list(
        ctx.db.exec(
            select(Memory).where(
                Memory.user_id == ctx.user_id,
                cast(Any, Memory.is_active),
                Memory.file_path.is_not(None),  # type: ignore[union-attr]
            )
        ).all()
    )


def _sync_new_disk_files(ctx: ElroyContext, disk_files: list[Path], disk_path_to_fm: dict[Path, dict[str, Any]]) -> None:
    from .operations import do_create_memory

    for path in disk_files:
        fm = disk_path_to_fm[path]
        if "id" in fm:
            continue
        text = read_memory_text(path)
        name = path.stem.replace("_", " ")
        try:
            memory = do_create_memory(ctx, name, text, [], False)
            assert memory.id is not None
            if memory.file_path and memory.file_path != str(path):
                new_path = Path(memory.file_path)
                if new_path.exists() and new_path != path:
                    new_path.unlink()
                memory.file_path = str(path)
                ctx.db.add(memory)
                ctx.db.commit()
            write_id_to_frontmatter(path, memory.id)
            logger.info(f"Created new memory from file {path.name}: id={memory.id}")
        except Exception as e:
            logger.error(f"Failed to create memory from file {path}: {e}", exc_info=True)


def _sync_existing_disk_files(ctx: ElroyContext, disk_id_to_path: dict[int, Path], db_id_to_memory: dict[int, Memory]) -> None:
    from ..recall.operations import upsert_embedding_if_needed

    for mid, disk_path in disk_id_to_path.items():
        db_memory = db_id_to_memory.get(mid)
        if db_memory is None:
            logger.warning(f"File {disk_path.name} has id={mid} but no active memory found in DB; ignoring")
            continue

        renamed = db_memory.file_path != str(disk_path)
        if renamed:
            old_name = db_memory.name
            db_memory.file_path = str(disk_path)
            db_memory.name = disk_path.stem.replace("_", " ")
            ctx.db.add(db_memory)
            ctx.db.commit()
            logger.info(f"Memory {mid} renamed: {old_name!r} -> {db_memory.name!r}, path updated")

        try:
            upsert_embedding_if_needed(ctx, db_memory)
        except Exception as e:
            logger.error(f"Failed to re-embed memory {mid} from file {disk_path}: {e}", exc_info=True)


def _mark_missing_disk_files(ctx: ElroyContext, db_file_memories: list[Memory]) -> None:
    from .operations import mark_inactive

    for db_memory in db_file_memories:
        if not db_memory.file_path:
            continue
        db_path = Path(db_memory.file_path)
        if db_path.exists():
            continue
        logger.info(f"Memory file disappeared: {db_path.name}; marking memory {db_memory.id} inactive")
        db_memory.file_path = None
        ctx.db.add(db_memory)
        ctx.db.commit()
        try:
            mark_inactive(ctx, db_memory)
        except Exception as e:
            logger.error(f"Failed to mark memory {db_memory.id} inactive: {e}", exc_info=True)


def sync_memory_files(ctx: ElroyContext) -> None:
    """Sync memory files in memory_dir with the DB.

    Handles:
    - New files (no frontmatter id): create Memory in DB, write id back
    - Renames (id in frontmatter, file_path in DB differs): update DB
    - Content changes (same path, different md5): re-embed
    - Disappeared files (DB has file_path, file gone): mark inactive
    """
    memory_dir = ctx.memory_dir_path
    if not memory_dir:
        return

    status_key = f"memory_sync_{ctx.user_id}"
    set_background_status(status_key, "syncing memories...")

    disk_files: list[Path] = [p for p in memory_dir.glob("*.md") if p.is_file()]
    disk_id_to_path, disk_path_to_fm = _index_disk_memory_files(disk_files)
    db_file_memories = _load_db_file_memories(ctx)
    db_id_to_memory: dict[int, Memory] = {m.id: m for m in db_file_memories if m.id}
    _sync_new_disk_files(ctx, disk_files, disk_path_to_fm)
    _sync_existing_disk_files(ctx, disk_id_to_path, db_id_to_memory)
    _mark_missing_disk_files(ctx, db_file_memories)

    clear_background_status(status_key)


def schedule_memory_file_sync(ctx: ElroyContext) -> Job | None:
    """Schedule periodic memory file sync if memory_dir is configured."""
    if not ctx.memory_dir:
        return None

    scheduler = get_scheduler()
    job_id = f"memory_file_sync___{ctx.user_id}"

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    interval_minutes = ctx.background_ingest_interval_minutes
    trigger = IntervalTrigger(minutes=interval_minutes)

    def wrapped_sync():
        new_ctx = ElroyContext(
            database_url=ctx.database_url,
            chroma_path=ctx.chroma_path,
            model_config=ctx.model_config,
            ui_config=ctx.ui_config,
            memory_config=ctx.memory_config,
            tool_config=ctx.tool_config,
            runtime_config=ctx.runtime_config,
        )
        from ...core.session import dbsession

        with dbsession(new_ctx):
            sync_memory_files(new_ctx)

    job = scheduler.add_job(
        wrapped_sync,
        trigger=trigger,
        id=job_id,
        replace_existing=True,
    )

    logger.info(f"Scheduled memory file sync every {interval_minutes} minutes for memory_dir={ctx.memory_dir} (job ID: {job_id})")

    return job
