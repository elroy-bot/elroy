import logging
import time
from datetime import UTC, datetime
from functools import partial
from typing import Iterator, Optional, TypeVar


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






def datetime_to_string(dt: datetime) -> str:
    return dt.strftime("%A, %B %d, %Y %I:%M %p %Z")


utc_epoch_to_datetime_string = lambda epoch: datetime_to_string(datetime.fromtimestamp(epoch, UTC))
