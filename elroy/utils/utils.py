import logging
import threading
import time
from datetime import datetime
from functools import partial
from typing import Any, Dict, Iterator, Optional, TypeVar

from pytz import UTC

from ..config.config import ElroyContext, session_manager

T = TypeVar("T")


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
        elif any(sensitive in k.lower() for sensitive in ("api_key", "password", "secret", "token")):
            result[k] = "[REDACTED]" if v else None
        else:
            result[k] = v
    return result


def run_in_background_thread(fn, context, *args):
    # hack to get a new session for the thread
    with session_manager(context.config.postgres_url) as session:
        thread = threading.Thread(
            target=fn,
            args=(ElroyContext(user_id=context.user_id, session=session, config=context.config, io=context.io), *args),
            daemon=True,
        )
        thread.start()
