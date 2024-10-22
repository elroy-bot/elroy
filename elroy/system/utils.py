import logging
import time
from datetime import UTC, datetime
from functools import partial
from typing import Iterable, Iterator, Optional, Type, TypeVar

from toolz import last

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


def last_or_none(iterable: Iterable[T]) -> Optional[T]:
    try:
        return last(iterable)
    except IndexError:
        return None


def assert_type(expected_type: Type, value: T) -> T:
    if not isinstance(value, expected_type):
        raise ValueError(f"Expected {expected_type} but got {type(value)}")
    else:
        return value


datetime_to_string = lambda date: date.strftime("%A, %B %d, %Y %I:%M %p %Z")


utc_epoch_to_datetime_string = lambda epoch: datetime_to_string(datetime.fromtimestamp(epoch, UTC))
