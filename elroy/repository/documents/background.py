"""Background document ingestion functionality."""

from apscheduler.job import Job
from apscheduler.triggers.interval import IntervalTrigger

from ...core.async_tasks import get_scheduler, schedule_task
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...core.services.background_sync import DocumentIngestionService
from ...core.status import clear_background_status, set_background_status
from ...utils.clock import utc_now

logger = get_logger()


def background_ingest_task(ctx: ElroyContext) -> None:
    """Background task to ingest documents from configured paths."""
    if not ctx.background_ingest_paths:
        logger.debug("No background ingest paths configured")
        return

    service = DocumentIngestionService(ctx)
    logger.info(f"Starting background ingestion for {len(ctx.background_ingest_paths)} paths")
    status_key = f"ingest_{ctx.user_id}"
    set_background_status(status_key, "ingesting documents...")
    start_time = utc_now()
    exclude = service.build_exclude_patterns()

    for target in service.iter_targets():
        try:
            service.ingest_target(target, exclude)
        except Exception as e:
            logger.error(f"Background ingestion failed for {target.path}: {e}", exc_info=True)

    logger.info("Background ingestion completed")
    clear_background_status(status_key)

    try:
        service.record_last_run(start_time)
    except Exception as e:
        logger.error(f"Failed to update background ingestion last run time: {e}", exc_info=True)


def schedule_periodic_ingestion(ctx: ElroyContext) -> Job | None:
    """Schedule periodic background ingestion if enabled."""
    if not ctx.background_ingest_enabled:
        logger.debug("Background ingestion is disabled")
        return None
    if not ctx.background_ingest_paths:
        logger.debug("No background ingest paths configured")
        return None

    scheduler = get_scheduler()
    job_id = f"background_ingest___{ctx.user_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    service = DocumentIngestionService(ctx)
    trigger = IntervalTrigger(minutes=ctx.background_ingest_interval_minutes)

    def wrapped_background_ingest():
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
            background_ingest_task(new_ctx)

    job = scheduler.add_job(
        wrapped_background_ingest,
        trigger=trigger,
        id=job_id,
        replace_existing=True,
    )

    logger.info(
        f"Scheduled background ingestion every {ctx.background_ingest_interval_minutes} "
        f"minutes for {len(ctx.background_ingest_paths)} paths (job ID: {job_id})"
    )
    schedule_task(background_ingest_task, ctx, delay_seconds=service.initial_delay_seconds())
    return job
