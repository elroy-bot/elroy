import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, Iterator, Optional, TypeVar

from ..config.ctx import ElroyContext
from ..config.initializer import dbsession

T = TypeVar("T")


def run_async(thread_pool: ThreadPoolExecutor, coro):
    """
    Runs a coroutine in a separate thread and returns the result (synchronously).

    Args:
        coro: The coroutine to run

    Returns:
        The result of the coroutine
    """

    return thread_pool.submit(asyncio.run, coro).result()


def is_blank(input: Optional[str]) -> bool:
    assert isinstance(input, (str, type(None)))
    return not input or not input.strip()


def first_or_none(iterable: Iterator[T]) -> Optional[T]:
    return next(iterable, None)


def last_or_none(iterable: Iterator[T]) -> Optional[T]:
    return next(reversed(list(iterable)), None)


def datetime_to_string(dt: Optional[datetime]) -> Optional[str]:
    if dt:
        return dt.strftime("%A, %B %d, %Y %I:%M %p %Z")


REDACT_KEYWORDS = ("api_key", "password", "secret", "token", "url")


def obscure_sensitive_info(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively process dictionary to obscure sensitive information.

    Args:
        d: Dictionary to process

    Returns:
        Dictionary with sensitive values replaced with '[REDACTED]'
    """
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = obscure_sensitive_info(v)
        elif isinstance(v, (list, tuple)):
            result[k] = [obscure_sensitive_info(i) if isinstance(i, dict) else i for i in v]
        elif any(sensitive in k.lower() for sensitive in REDACT_KEYWORDS):
            result[k] = "[REDACTED]" if v else None
        elif any(sensitive in str(v).lower() for sensitive in REDACT_KEYWORDS):
            result[k] = "[REDACTED]" if v else None
        else:
            result[k] = v
    return result


def run_in_background(fn: Callable, ctx: ElroyContext, *args) -> Optional[threading.Thread]:
    from ..config.ctx import ElroyContext

    if not ctx.use_background_threads:
        logging.debug("Background threads are disabled. Running function in the main thread.")
        fn(ctx, *args)
        return

    # hack to get a new session for the thread
    def wrapped_fn():
        # Create completely new connection in the new thread
        new_ctx = ElroyContext(**vars(ctx.params))
        with dbsession(new_ctx):
            fn(new_ctx, *args)

    thread = threading.Thread(
        target=wrapped_fn,
        daemon=True,
    )
    thread.start()
    logging.info("Running background thread")
    return thread
