"""Background memory file sync for file-backed memories (Obsidian integration)."""

from apscheduler.job import Job
from apscheduler.triggers.interval import IntervalTrigger

from ...core.async_tasks import get_scheduler
from ...core.ctx import ElroyConfig
from ...core.logging import get_logger
from ...core.memory_file_sync import MemoryFileSyncOrchestrator
from ...core.runtime import build_memory_file_sync_runtime
from ...core.session import build_elroy_session, clone_config, invoke_with_config, open_turn_context
from ...core.status import clear_background_status, set_background_status
from ...core.turn import TurnContext
from ..user.session import build_user_session

logger = get_logger()
DEFAULT_MEMORY_FILE_SYNC_INTERVAL_MINUTES = 60


def sync_memory_files(turn: TurnContext) -> None:
    """Sync memory files in memory_dir with the DB."""
    memory_dir = build_memory_file_sync_runtime(turn).memory_dir_path
    if not memory_dir:
        return

    status_key = f"memory_sync_{build_user_session(turn).user_id}"
    set_background_status(status_key, "syncing memories...")
    service = MemoryFileSyncOrchestrator(turn)
    service.apply_plan(service.build_plan())
    clear_background_status(status_key)


def schedule_memory_file_sync(ctx: ElroyConfig) -> Job | None:
    """Schedule periodic memory file sync if memory_dir is configured."""
    scheduler = get_scheduler()
    with open_turn_context(ctx, build_elroy_session(ctx)) as turn:
        runtime = build_memory_file_sync_runtime(turn)
        if not runtime.memory_dir_path:
            return None
        job_id = f"memory_file_sync___{build_user_session(turn).user_id}"

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    trigger = IntervalTrigger(minutes=DEFAULT_MEMORY_FILE_SYNC_INTERVAL_MINUTES)

    def wrapped_sync():
        new_ctx = clone_config(ctx)
        invoke_with_config(sync_memory_files, new_ctx)

    job = scheduler.add_job(
        wrapped_sync,
        trigger=trigger,
        id=job_id,
        replace_existing=True,
    )

    logger.info(
        f"Scheduled memory file sync every {DEFAULT_MEMORY_FILE_SYNC_INTERVAL_MINUTES} "
        f"minutes for memory_dir={runtime.memory_dir_path} (job ID: {job_id})"
    )
    return job
