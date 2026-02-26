"""Background memory file sync for file-backed memories (Obsidian integration)."""

from pathlib import Path
from typing import Any, cast

from apscheduler.job import Job
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import select

from ...core.async_tasks import get_scheduler
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import Memory
from .file_storage import (
    read_memory_frontmatter,
    read_memory_text,
    write_id_to_frontmatter,
)

logger = get_logger()


def sync_memory_files(ctx: ElroyContext) -> None:
    """Sync memory files in memory_dir with the DB.

    Handles:
    - New files (no frontmatter id): create Memory in DB, write id back
    - Renames (id in frontmatter, file_path in DB differs): update DB
    - Content changes (same path, different md5): re-embed
    - Disappeared files (DB has file_path, file gone): mark inactive
    """
    from ..recall.operations import upsert_embedding_if_needed
    from .operations import do_create_memory, mark_inactive

    memory_dir = ctx.memory_dir_path
    if not memory_dir:
        return

    # Scan all .md files in memory_dir root (non-recursive, skip archive/)
    disk_files: list[Path] = [p for p in memory_dir.glob("*.md") if p.is_file()]

    # Build index: id -> path from frontmatter
    disk_id_to_path: dict[int, Path] = {}
    disk_path_to_fm: dict[Path, dict[str, Any]] = {}
    for path in disk_files:
        fm = read_memory_frontmatter(path)
        disk_path_to_fm[path] = fm
        if "id" in fm:
            try:
                mid = int(fm["id"])
                disk_id_to_path[mid] = path
            except (ValueError, TypeError):
                pass

    # Load all file-backed memories from DB for this user
    db_file_memories: list[Memory] = list(
        ctx.db.exec(
            select(Memory).where(
                Memory.user_id == ctx.user_id,
                cast(Any, Memory.is_active),
                Memory.file_path.is_not(None),  # type: ignore[union-attr]
            )
        ).all()
    )
    # Index by id
    db_id_to_memory: dict[int, Memory] = {m.id: m for m in db_file_memories if m.id}

    # --- Handle new files (no frontmatter id) ---
    for path in disk_files:
        fm = disk_path_to_fm[path]
        if "id" not in fm:
            # New file created outside Elroy
            text = read_memory_text(path)
            name = path.stem.replace("_", " ")
            try:
                memory = do_create_memory(ctx, name, text, [], False)
                assert memory.id is not None
                # Write id back to frontmatter. If memory_dir is set,
                # do_create_memory will have written the file already at a
                # possibly different path. For externally-created files we
                # need to update the file_path in DB and write the id to the
                # original file.
                if memory.file_path and memory.file_path != str(path):
                    # do_create_memory wrote a new file; remove it and use the
                    # original file instead.
                    new_path = Path(memory.file_path)
                    if new_path.exists() and new_path != path:
                        new_path.unlink()
                    memory.file_path = str(path)
                    memory.text = None
                    ctx.db.add(memory)
                    ctx.db.commit()
                    write_id_to_frontmatter(path, memory.id)
                else:
                    write_id_to_frontmatter(path, memory.id)
                logger.info(f"Created new memory from file {path.name}: id={memory.id}")
            except Exception as e:
                logger.error(f"Failed to create memory from file {path}: {e}", exc_info=True)
            continue

    # --- Handle renames and content changes for files with ids ---
    for mid, disk_path in disk_id_to_path.items():
        db_memory = db_id_to_memory.get(mid)
        if db_memory is None:
            # Memory id not found in DB (may have been deleted externally or id is wrong)
            logger.warning(f"File {disk_path.name} has id={mid} but no active memory found in DB; ignoring")
            continue

        db_file_path = db_memory.file_path
        renamed = db_file_path != str(disk_path)

        if renamed:
            # Rename: update file_path and name in DB
            old_name = db_memory.name
            new_name = disk_path.stem.replace("_", " ")
            db_memory.file_path = str(disk_path)
            db_memory.name = new_name
            db_memory.text = None
            ctx.db.add(db_memory)
            ctx.db.commit()
            logger.info(f"Memory {mid} renamed: {old_name!r} -> {new_name!r}, path updated")

        # Check content change via re-embedding (upsert_embedding_if_needed compares md5)
        try:
            upsert_embedding_if_needed(ctx, db_memory)
        except Exception as e:
            logger.error(f"Failed to re-embed memory {mid} from file {disk_path}: {e}", exc_info=True)

    # --- Handle disappeared files ---
    for db_memory in db_file_memories:
        if not db_memory.file_path:
            continue
        db_path = Path(db_memory.file_path)
        if not db_path.exists():
            # File gone — mark inactive, no archive (file is already gone)
            logger.info(f"Memory file disappeared: {db_path.name}; marking memory {db_memory.id} inactive")
            # Temporarily clear file_path so mark_inactive doesn't try to archive
            db_memory.file_path = None
            ctx.db.add(db_memory)
            ctx.db.commit()
            try:
                mark_inactive(ctx, db_memory)
            except Exception as e:
                logger.error(f"Failed to mark memory {db_memory.id} inactive: {e}", exc_info=True)


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
            database_config=ctx.database_config,
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
