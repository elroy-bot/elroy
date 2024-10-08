import logging
import re
import time
from datetime import datetime
from functools import partial
from typing import Iterable, Optional, Type, TypeVar

from toolz import first, last, pipe
from toolz.curried import do

from elroy.system.parameters import INNER_THOUGHT_TAG

T = TypeVar("T")
U = TypeVar("U")


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


def first_or_none(iterable: Iterable[T]) -> Optional[T]:
    try:
        return first(iterable)
    except IndexError:
        return None


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


date_to_string = lambda date: date.strftime("%A, %B %d, %Y %I:%M %p %Z")

utc_epoch_to_string = lambda epoch: date_to_string(datetime.utcfromtimestamp(epoch))


def extract_xml_tag_content(tag: str, xml_string: str) -> Optional[str]:
    # Define the regex pattern
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, xml_string, flags=re.DOTALL)

    # Extract and return the matched text, if found
    if match:
        return match.group(1).strip()
    else:
        return None


def parse_tag(tag: str, xml_string: str):
    return pipe(
        xml_string,
        partial(extract_xml_tag_content, tag),
        do(lambda x: logging.debug(f"Could not find tag {tag} in xml_string") if x is None else None),
        lambda x: x or xml_string,
    )


parse_internal_monologue = partial(parse_tag, INNER_THOUGHT_TAG)
