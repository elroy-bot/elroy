import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Iterator, Optional, TypeVar, Union

from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..core.session import dbsession

T = TypeVar("T")

logger = get_logger()


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


def first_or_none(x: Union[Iterator[T], Iterable[T]]) -> Optional[T]:  # noqa
    if isinstance(x, Iterator):
        return next(x, None)
    elif not isinstance(x, Iterator) and isinstance(x, Iterable):
        return next(iter(x), None)
    else:
        raise ValueError(f"Expected an iterable or iterator, got {x}")


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
    from ..core.ctx import ElroyContext

    if not ctx.use_background_threads:
        logger.debug("Background threads are disabled. Running function in the main thread.")
        fn(ctx, *args)
        return

    # hack to get a new session for the thread
    def wrapped_fn():
        # Create completely new connection in the new thread
        new_ctx = ElroyContext(
            database_config=ctx.database_config,
            model_config=ctx.model_config,
            ui_config=ctx.ui_config,
            memory_config=ctx.memory_config,
            tool_config=ctx.tool_config,
            runtime_config=ctx.runtime_config,
        )
        with dbsession(new_ctx):
            fn(new_ctx, *args)

    thread = threading.Thread(
        target=wrapped_fn,
        daemon=True,
    )
    thread.start()
    logger.info("Running background thread")
    return thread
