import logging
from functools import wraps
from typing import Callable, Optional

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.job import Job
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..core.session import dbsession
from ..io.live_panel import JobStatus

logger = get_logger()

# Global scheduler instance
scheduler = None


def init_scheduler():
    """Initialize the APScheduler instance."""
    global scheduler

    if scheduler is not None:
        logger.info("Scheduler already initialized")
        return scheduler

    # Configure job stores and executors
    jobstores = {"default": MemoryJobStore()}
    executors = {"default": ThreadPoolExecutor(20)}

    # Create and configure the scheduler
    scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, logger=logging.getLogger("apscheduler"))

    # Start the scheduler
    scheduler.start()
    logger.info("APScheduler started")

    return scheduler


def get_scheduler():
    """Get the global scheduler instance, initializing it if necessary."""
    global scheduler
    if scheduler is None:
        return init_scheduler()
    return scheduler


def schedule_task(
    fn: Callable,
    ctx: ElroyContext,
    *args,
    replace: bool = False,
    delay_seconds: Optional[int] = None,
    job_name: Optional[str] = None,
    **kwargs,
) -> Optional[Job]:
    """
    Schedule a task to run in the background using APScheduler.
    This is a replacement for the run_in_background function.

    Args:
        fn: The function to run
        ctx: The ElroyContext instance
        *args: Arguments to pass to the function
        replace: If True, replace existing job with same ID
        delay_seconds: Optional delay in seconds before running the task. If not provided, runs immediately.
        job_name: Optional human-readable name for the job (for Live panel display)
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The scheduled job or None if background threads are disabled
    """
    if not ctx.use_background_threads:
        logger.debug("Background threads are disabled. Running function in the main thread.")
        fn(ctx, *args, **kwargs)
        return None

    # Get the live panel manager if available
    live_panel = getattr(ctx, "_live_panel", None)
    display_name = job_name or fn.__name__

    # Get the scheduler and determine job parameters first
    scheduler = get_scheduler()

    # Determine job parameters
    job_kwargs = {}
    if replace:
        job_kwargs["id"] = fn.__name__ + "___" + str(ctx.user_id)
        job_kwargs["replace_existing"] = True

    if delay_seconds is not None:
        from datetime import datetime, timedelta

        run_time = datetime.now() + timedelta(seconds=delay_seconds)
        job_kwargs["run_date"] = run_time

    # Create a wrapper function that sets up a new database session
    @wraps(fn)
    def wrapped_fn():
        job_id = None
        try:
            # Create completely new connection in the new thread
            new_ctx = ElroyContext(**vars(ctx.params))

            # Get current job ID for status updates
            if "id" in job_kwargs:
                current_job = scheduler.get_job(job_kwargs["id"])
                if current_job:
                    job_id = current_job.id
                    if live_panel:
                        live_panel.update_job(job_id, status=JobStatus.RUNNING)

            with dbsession(new_ctx):
                fn(new_ctx, *args, **kwargs)

            # Mark job as completed
            if live_panel and job_id:
                live_panel.complete_job(job_id, progress="Task completed successfully")

        except Exception as e:
            logger.error(f"Task {fn.__name__} failed with error: {e}")
            if live_panel and job_id:
                live_panel.fail_job(job_id, str(e))
            raise

    job = scheduler.add_job(wrapped_fn, "date", **job_kwargs)

    # Add job to live panel if available
    if live_panel:
        status = JobStatus.SCHEDULED if delay_seconds else JobStatus.RUNNING
        live_panel.add_job(job.id, display_name, status)

    if delay_seconds is not None:
        logger.info(f"Scheduled task {fn.__name__} to run in {delay_seconds} seconds with job ID {job.id}")
    else:
        logger.info(f"Scheduled task {fn.__name__} with job ID {job.id}")
    return job


def shutdown_scheduler(wait: bool = True):
    """Shutdown the scheduler when the application exits."""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=wait)
        scheduler = None
        logger.info("APScheduler shutdown")
