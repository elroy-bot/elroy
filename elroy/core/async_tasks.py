import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from typing import Callable, Optional

from apscheduler.executors.pool import ThreadPoolExecutor as APThreadPoolExecutor
from apscheduler.job import Job
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from ..core.ctx import ElroyContext
from ..core.logging import get_logger

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
    executors = {"default": APThreadPoolExecutor(20)}

    # Create and configure the scheduler
    scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, logger=logging.getLogger("apscheduler"))

    # Start the scheduler
    scheduler.start()
    logger.info("APScheduler started")

    return scheduler


def with_new_session(ctx: ElroyContext, inject_ctx: bool = True):
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from ..core.session import dbsession

            new_ctx = ElroyContext(**vars(ctx.params))
            with dbsession(new_ctx):
                if inject_ctx:
                    return fn(new_ctx, *args, **kwargs)
                else:
                    return fn(*args, **kwargs)

        return wrapper

    return decorator


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

    job = scheduler.add_job(with_new_session(ctx)(fn), "date", **job_kwargs)

    if delay_seconds is not None:
        logger.info(f"Scheduled task {fn.__name__} to run in {delay_seconds} seconds with job ID {job.id}")
    else:
        logger.info(f"Scheduled task {fn.__name__} with job ID {job.id}")
    return job


def run_async(thread_pool: ThreadPoolExecutor, coro):
    """
    Runs a coroutine in a separate thread and returns the result (synchronously).

    Args:
        coro: The coroutine to run

    Returns:
        The result of the coroutine
    """

    return thread_pool.submit(asyncio.run, coro).result()


def juxt(ctx: ElroyContext, *functions):
    """
    Creates a function that applies multiple functions to the same arguments
    in parallel and returns a tuple of results.
    """

    def _juxt_func(*args, **kwargs):
        futures = []
        for fn in functions:
            futures.append(ctx.thread_pool.submit(with_new_session(ctx)(fn), *args, **kwargs))
        return tuple([future.result() for future in as_completed(futures)])

    return _juxt_func


def shutdown_scheduler(wait: bool = True):
    """Shutdown the scheduler when the application exits."""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=wait)
        scheduler = None
        logger.info("APScheduler shutdown")
