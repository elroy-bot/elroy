import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Generator, Optional

import pytz
from pytz import UTC

from elroy.config import is_test_env


class FakeClock:
    frozen_time: Optional[datetime] = None
    offset: timedelta = timedelta()

    @classmethod
    def get_utc_now(cls) -> datetime:
        if cls.frozen_time:
            return cls.frozen_time
        else:
            return datetime.now(UTC) + cls.offset

    @classmethod
    def advance(cls, delta: timedelta) -> None:
        if cls.frozen_time:
            cls._set_frozen_time(cls.frozen_time + delta)
        else:
            cls.set_offset(cls.offset + delta)

    @classmethod
    def freeze_time(cls, time: datetime) -> None:
        cls._set_frozen_time(time)

    @classmethod
    def reset(cls) -> None:
        cls.set_offset(timedelta())

    @classmethod
    def start(cls) -> None:
        assert cls.frozen_time
        cls.set_offset(cls.frozen_time - cls.get_utc_now())

    @classmethod
    def stop(cls) -> None:
        assert cls.frozen_time is None

        cls._set_frozen_time(cls.get_utc_now() + cls.offset)

    @classmethod
    def set_offset(cls, offset: timedelta) -> None:
        """
        Either an offset or a frozen time can be set, but not both.
        """
        cls.frozen_time = None
        cls.offset = offset

    @classmethod
    def _set_frozen_time(cls, dt: datetime) -> None:
        assert cls.frozen_time is not None

        cls.frozen_time = dt
        cls.offset = timedelta()


@contextmanager
def clock_starting_at(time: datetime) -> Generator[None, None, None]:
    FakeClock.set_offset(time - FakeClock.get_utc_now())
    try:
        yield
    finally:
        FakeClock.reset()


if is_test_env():
    get_utc_now = FakeClock.get_utc_now
else:
    get_utc_now = lambda: datetime.now(UTC)


def get_now(tz: str) -> datetime:
    return get_utc_now().astimezone(pytz.timezone(tz))


def string_to_timedelta(time_to_completion: str) -> timedelta:
    # validate that the time_to_completion is in the form of NUMBER TIME_UNIT
    # where TIME_UNIT is one of HOUR, DAY, WEEK, MONTH
    # return the timedelta

    logging.debug("Converting time to completion string to timedelta: '%s'", time_to_completion)

    time_amount, time_unit = time_to_completion.lower().strip().split()

    if time_unit[-1] != "s":
        time_unit += "s"

    if not time_amount.isdigit():
        raise ValueError(f"Invalid time number {time_to_completion.split()[0]}. Must be an integer")

    if time_unit in ["hours", "days", "weeks"]:
        return timedelta(**{time_unit: int(time_amount)})
    elif time_unit == "months":
        return timedelta(days=int(time_amount) * 30)  # approximate
    elif time_unit == "years":
        return timedelta(days=int(time_amount) * 365)  # approximate
    else:
        raise ValueError(f"Invalid time unit: {time_to_completion.split()[1]}. Must be one of HOURS, DAYS, WEEKS, MONTHS, or YEARS.")
