import logging
from collections.abc import Callable
from functools import wraps

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.job import Job
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from ..core.logging import get_logger
from ..core.runtime import build_background_task_runtime
from ..core.session import build_elroy_session, clone_config, invoke_with_config, open_turn_context
from ..core.turn import TurnContext
from ..repository.user.session import build_user_session

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
    turn: TurnContext,
    *args,
    replace: bool = False,
    delay_seconds: int | None = None,
    **kwargs,
) -> Job | None:
    """
    Args:
        fn: The function to run
        turn: The execution turn
        *args: Arguments to pass to the function
        job_key: Optional job key for replacement behavior. If provided, will replace existing job with same key.
        delay_seconds: Optional delay in seconds before running the task. If not provided, runs immediately.
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The scheduled job or None if background threads are disabled
    """
    ctx = turn.config
    runtime = build_background_task_runtime(ctx)
    if not runtime.use_background_threads:
        logger.debug("Background threads are disabled. Running function in the main thread.")
        fn(turn, *args, **kwargs)
        return None

    # Create a wrapper function that sets up a new database session
    @wraps(fn)
    def wrapped_fn():
        new_ctx = clone_config(ctx)
        invoke_with_config(fn, new_ctx, *args, **kwargs)

    # Get the scheduler and add the job
    scheduler = get_scheduler()

    # Determine job parameters
    job_kwargs = {}
    if replace is not None:
        fn_name = getattr(fn, "__name__", "unknown")
        with open_turn_context(ctx, build_elroy_session(ctx)) as turn:
            job_kwargs["id"] = fn_name + "___" + str(build_user_session(turn).user_id)
        job_kwargs["replace_existing"] = True

    if delay_seconds is not None:
        from datetime import datetime, timedelta

        run_time = datetime.now() + timedelta(seconds=delay_seconds)
        job_kwargs["run_date"] = run_time

    job = scheduler.add_job(wrapped_fn, "date", **job_kwargs)

    fn_name = getattr(fn, "__name__", "unknown")
    if delay_seconds is not None:
        logger.info(f"Scheduled task {fn_name} to run in {delay_seconds} seconds with job ID {job.id}")
    else:
        logger.info(f"Scheduled task {fn_name} with job ID {job.id}")
    return job


def shutdown_scheduler(wait: bool = True):
    """Shutdown the scheduler when the application exits."""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=wait)
        scheduler = None
        logger.info("APScheduler shutdown")
