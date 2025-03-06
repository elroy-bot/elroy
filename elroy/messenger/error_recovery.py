from functools import wraps
from time import sleep
from typing import Callable, Iterator, ParamSpec, TypeVar

from httpx import RemoteProtocolError

from ..core.logging import get_logger

logger = get_logger()


T = TypeVar("T")
P = ParamSpec("P")


def retry_completion_api_stream(func: Callable[P, Iterator[T]]) -> Callable[P, Iterator[T]]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Iterator[T]:

        attempt = 0
        while True:
            try:
                yield from func(*args, **kwargs)
                break
            except Exception as e:
                _handle_error(e, attempt)
                attempt += 1

    return wrapper


def retry_completion_api_return(func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator that handles remote protocol errors by retrying the function.
    For functions that return values (not generators).

    Args:
        func: The function to decorate

    Returns:
        A wrapped function that handles remote protocol errors
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        attempt = 0
        while True:
            try:
                # For regular functions, just return the result
                return func(*args, **kwargs)
            except Exception as e:
                _handle_error(e, attempt)
                attempt += 1

    return wrapper


def _handle_error(e: Exception, attempt: int):
    from litellm.exceptions import APIConnectionError, APIError

    if type(e) in [RemoteProtocolError, APIConnectionError, APIError]:
        if attempt >= 5:
            logger.warning("Retries exhausted")
            raise
        logger.warning(f"Remote protocol error: {str(e)}")
        sleep_duration_secs = 2**attempt
        logger.warning(f"Retrying in {sleep_duration_secs} seconds")
        sleep(sleep_duration_secs)
    else:
        logger.error(f"Unexpected error: {str(e)}")
        raise
