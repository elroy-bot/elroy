"""Background document ingestion functionality."""

from datetime import timedelta
from pathlib import Path
from typing import Optional

from apscheduler.job import Job
from apscheduler.triggers.interval import IntervalTrigger

from ...core.async_tasks import get_scheduler, schedule_task
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...repository.user.operations import get_or_create_user_preference
from ...utils.clock import utc_now
from .operations import do_ingest, do_ingest_dir

logger = get_logger()


def background_ingest_task(ctx: ElroyContext) -> None:
    """
    Background task to ingest documents from configured paths.
    This runs in a background thread via APScheduler.
    """
    paths = ctx.background_ingest_paths

    if not paths:
        logger.debug("No background ingest paths configured")
        return

    logger.info(f"Starting background ingestion for {len(paths)} paths")

    # Record the start time
    start_time = utc_now()

    for path_str in paths:
        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            logger.warning(f"Background ingest path does not exist: {path}")
            continue

        try:
            if path.is_file():
                result = do_ingest(ctx, path, force_refresh=False)
                logger.info(f"Background ingested {path}: {result.name}")
            elif path.is_dir():
                # Process directory without progress display (background mode)
                total_processed = 0
                for status_update in do_ingest_dir(
                    ctx,
                    path,
                    force_refresh=False,
                    recursive=True,
                    include=[],
                    exclude=[],
                ):
                    total_processed = sum(status_update.statuses.values())

                logger.info(f"Background ingested directory {path}: {total_processed} files processed")
        except Exception as e:
            logger.error(f"Background ingestion failed for {path}: {e}", exc_info=True)

    logger.info("Background ingestion completed")

    # Update the last run time in user preferences
    try:
        user_pref = get_or_create_user_preference(ctx)
        user_pref.background_ingest_last_run = start_time
        ctx.db.session.add(user_pref)
        ctx.db.session.commit()
        logger.debug(f"Recorded background ingestion last run time: {start_time}")
    except Exception as e:
        logger.error(f"Failed to update background ingestion last run time: {e}", exc_info=True)


def schedule_periodic_ingestion(ctx: ElroyContext) -> Optional[Job]:
    """
    Schedule periodic background ingestion if enabled.

    This should be called during agent startup.

    Args:
        ctx: The Elroy context

    Returns:
        The scheduled job, or None if background ingestion is disabled
    """
    if not ctx.background_ingest_enabled:
        logger.debug("Background ingestion is disabled")
        return None

    if not ctx.background_ingest_paths:
        logger.debug("No background ingest paths configured")
        return None

    scheduler = get_scheduler()

    job_id = f"background_ingest___{ctx.user_id}"

    # Remove existing job if present
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    # Check when background ingestion last ran
    user_pref = get_or_create_user_preference(ctx)
    last_run = user_pref.background_ingest_last_run
    interval_minutes = ctx.background_ingest_interval_minutes
    now = utc_now()

    # Calculate initial delay
    if last_run is None:
        # Never run before - start after short delay
        initial_delay_seconds = 10
        logger.info("Background ingestion has never run - scheduling first run in 10 seconds")
    else:
        # Calculate when next run should be based on last run
        next_run_time = last_run + timedelta(minutes=interval_minutes)
        time_until_next = (next_run_time - now).total_seconds()

        if time_until_next <= 0:
            # Next run is overdue - run immediately
            initial_delay_seconds = 10
            logger.info(
                f"Background ingestion last ran {(now - last_run).total_seconds() / 60:.1f} minutes ago - " f"scheduling immediate run"
            )
        else:
            # Schedule for the calculated time
            initial_delay_seconds = int(time_until_next)
            logger.info(
                f"Background ingestion last ran {(now - last_run).total_seconds() / 60:.1f} minutes ago - "
                f"scheduling next run in {time_until_next / 60:.1f} minutes"
            )

    # Schedule recurring job using IntervalTrigger
    trigger = IntervalTrigger(minutes=interval_minutes)

    # Create a wrapper function for the scheduler
    def wrapped_background_ingest():
        """Wrapper to create a new context for background ingestion."""
        # Create completely new connection in the new thread
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

    # Schedule initial run with calculated delay
    schedule_task(background_ingest_task, ctx, delay_seconds=initial_delay_seconds)

    return job
