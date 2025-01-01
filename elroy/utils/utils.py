import asyncio
import logging
import threading
import time
from datetime import datetime
from functools import partial
from typing import Any, Callable, Dict, Iterator, Optional, TypeVar

from pytz import UTC

from ..config.ctx import ElroyContext, clone_ctx_with_db

T = TypeVar("T")


def is_truthy(input: Any) -> bool:
    if isinstance(input, str):
        return not is_blank(input)
    else:
        return bool(input)


def is_blank(input: Optional[str]) -> bool:
    assert isinstance(input, (str, type(None)))
    return not input or not input.strip()


def logged_exec_time(func, name: Optional[str] = None):
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


utc_epoch_to_datetime_string = lambda epoch: datetime_to_string(datetime.fromtimestamp(epoch, UTC))

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

    assert isinstance(ctx, ElroyContext)

    def run_async_function():
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Run the async function in the event loop
        loop.run_until_complete(fn(new_ctx, *args))
        loop.close()

    # hack to get a new session for the thread
    with ctx.db.get_new_session() as db:
        new_ctx = clone_ctx_with_db(ctx, db)

        if asyncio.iscoroutinefunction(fn):
            # If the function is async, run it in a new thread with an event loop
            thread = threading.Thread(target=run_async_function, daemon=True)
        else:
            thread = threading.Thread(
                target=fn,
                args=(new_ctx, *args),
                daemon=True,
            )
        thread.start()
