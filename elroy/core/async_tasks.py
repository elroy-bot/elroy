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
    **kwargs,
) -> Optional[Job]:
    """
    Args:
        fn: The function to run
        ctx: The ElroyContext instance
        *args: Arguments to pass to the function
        job_key: Optional job key for replacement behavior. If provided, will replace existing job with same key.
        delay_seconds: Optional delay in seconds before running the task. If not provided, runs immediately.
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The scheduled job or None if background threads are disabled
    """
    if not ctx.use_background_threads:
        logger.debug("Background threads are disabled. Running function in the main thread.")
        fn(ctx, *args, **kwargs)
        return None

    # Create a wrapper function that sets up a new database session
    @wraps(fn)
    def wrapped_fn():
        # Create completely new connection in the new thread
        # Use config objects directly - much cleaner than extracting individual parameters
        new_ctx = ElroyContext(
            database_config=ctx.database_config,
            model_config=ctx.model_config,
            ui_config=ctx.ui_config,
            memory_config=ctx.memory_config,
            tool_config=ctx.tool_config,
            runtime_config=ctx.runtime_config,
        )
        with dbsession(new_ctx):
            fn(new_ctx, *args, **kwargs)

    # Get the scheduler and add the job
    scheduler = get_scheduler()

    # Determine job parameters
    job_kwargs = {}
    if replace is not None:
        job_kwargs["id"] = fn.__name__ + "___" + str(ctx.user_id)
        job_kwargs["replace_existing"] = True

    if delay_seconds is not None:
        from datetime import datetime, timedelta

        run_time = datetime.now() + timedelta(seconds=delay_seconds)
        job_kwargs["run_date"] = run_time

    job = scheduler.add_job(wrapped_fn, "date", **job_kwargs)

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
