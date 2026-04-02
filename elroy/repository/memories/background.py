"""Background memory file sync for file-backed memories (Obsidian integration)."""

from apscheduler.job import Job
from apscheduler.triggers.interval import IntervalTrigger

from ...core.async_tasks import get_scheduler
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...core.services.background_sync import MemoryFileSyncService
from ...core.status import clear_background_status, set_background_status

logger = get_logger()


def sync_memory_files(ctx: ElroyContext) -> None:
    """Sync memory files in memory_dir with the DB."""
    memory_dir = ctx.memory_dir_path
    if not memory_dir:
        return

    status_key = f"memory_sync_{ctx.user_id}"
    set_background_status(status_key, "syncing memories...")
    service = MemoryFileSyncService(ctx)
    service.apply_plan(service.build_plan())
    clear_background_status(status_key)


def schedule_memory_file_sync(ctx: ElroyContext) -> Job | None:
    """Schedule periodic memory file sync if memory_dir is configured."""
    if not ctx.memory_dir:
        return None

    scheduler = get_scheduler()
    job_id = f"memory_file_sync___{ctx.user_id}"

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    trigger = IntervalTrigger(minutes=ctx.background_ingest_interval_minutes)

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

    logger.info(
        f"Scheduled memory file sync every {ctx.background_ingest_interval_minutes} "
        f"minutes for memory_dir={ctx.memory_dir} (job ID: {job_id})"
    )
    return job
