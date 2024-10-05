import logging
import random
import time
from contextlib import contextmanager
from typing import Optional

from pyrate_limiter import BucketFullException, Duration, Limiter, Rate
from toolz import pipe
from toolz.curried import do

from elroy.system.clock import get_utc_now

NON_PREMIUM_DAILY_MESSAGE_LIMIT = 100
DAILY_WARNING_LIMIT = 20

rate_limits = {}


def _try_acquire(key: str, rate: Rate, raise_error: Optional[Exception] = None) -> bool:
    global rate_limits

    try:
        if key not in rate_limits:
            rate_limits[key] = {}
        if id not in rate_limits[key]:
            rate_limits[key][id] = Limiter(rate)

        rate_limits[key][id].try_acquire(key)
        return True
    except BucketFullException:
        if raise_error:
            raise raise_error
        else:
            return False


class RateLimitExceeded(Exception):
    pass


class DailyRateLimitExceeded(Exception):
    pass


@contextmanager
def rate_limit(key, calls_per_second, max_retries=3):
    """
    A context manager to apply rate limiting with retry logic.

    :param limit: The number of allowed calls
    :param period: The time period in seconds
    :param key: A unique key for this rate limit
    :param max_retries: Maximum number of retries
    :param initial_backoff: Initial backoff time in seconds
    """

    retries = 0
    initial_backoff_secs = 1
    while True:
        if _try_acquire(key, Rate(calls_per_second, Duration.SECOND)):
            try:
                yield
            finally:
                pass  # No cleanup needed
            return
        elif retries < max_retries:
            pipe(
                retries,
                lambda _: _ + 1,
                do(lambda _: logging.info(f"Rate limit for {key} exceeded, retry. Attempt: {_}")),
                lambda _: initial_backoff_secs * (2 ** (_ - 1)),
                lambda _: _ + random.uniform(0, 0.1 * _),
                time.sleep,
            )
        else:
            raise RateLimitExceeded(f"Rate limit exceeded for {key} after {max_retries} retries")


def daily_rate_limit(max_calls: int, key: str) -> None:
    """
    Apply a daily rate limit based on UTC calendar day.

    :param key: A unique key for this rate limit
    :param max_calls: The maximum number of calls allowed per UTC calendar day
    :raises DailyRateLimitExceeded: If the daily rate limit is exceeded
    """

    # Create a unique key for the current UTC day
    current_utc_day = get_utc_now().date().isoformat()
    daily_key = f"{key}:{current_utc_day}"

    _try_acquire(daily_key, Rate(max_calls, Duration.DAY), DailyRateLimitExceeded())

    # If we've reached this point, the rate limit was not exceeded
    logging.info(f"Daily rate limit check passed for {key}")


def is_within_non_premium_daily_message_limit(user_id: int) -> bool:
    try:
        daily_rate_limit(NON_PREMIUM_DAILY_MESSAGE_LIMIT, f"non_premium_daily_message_limit:{user_id}")
        return True
    except DailyRateLimitExceeded:
        return False


def is_within_daily_warning_message_limit(user_id: int) -> bool:
    try:
        daily_rate_limit(DAILY_WARNING_LIMIT, f"daily_warning_message_limit:{user_id}")
        return True
    except DailyRateLimitExceeded:
        return False
