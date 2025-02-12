import asyncio
import logging
import threading
import time
from datetime import datetime
from functools import partial, wraps
from typing import Any, Callable, Dict, Iterator, Optional, TypeVar

from ..config.ctx import ElroyContext

T = TypeVar("T")


def do_asyncio_run(coro):
    """
    Safely run an async coroutine, whether or not there's an existing event loop.

    Args:
        coro: The coroutine to run

    Returns:
        The result of the coroutine
    """
    loop = asyncio._get_running_loop()
    if loop is not None:
        return loop.run_until_complete(coro)
    else:
        return asyncio.run(coro)


def is_blank(input: Optional[str]) -> bool:
    assert isinstance(input, (str, type(None)))
    return not input or not input.strip()


def logged_exec_time(func, name: Optional[str] = None):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed_time = time.time() - start_time

        if name:
            func_name = name
        else:
            func_name = func.__name__ if not isinstance(func, partial) else func.func.__name__

        logging.info(f"Function '{func_name}' executed in {elapsed_time:.4f} seconds")
        return result

    return wrapper


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


def run_in_background_thread(fn: Callable, ctx: ElroyContext, *args):
    from ..config.ctx import ElroyContext

    # hack to get a new session for the thread

    def wrapped_fn():
        # Create completely new connection in the new thread
        new_ctx = ElroyContext(**vars(ctx.params))
        with new_ctx.dbsession():
            fn(new_ctx, *args)

    with ctx.db.get_new_session() as db:

        thread = threading.Thread(
            target=wrapped_fn,
            daemon=True,
        )
        thread.start()
