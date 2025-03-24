from datetime import datetime, timedelta, tzinfo

import pytz
from pytz import UTC

from ..core.logging import get_logger

logger = get_logger()


class Clock:
    now = datetime.now

    def utc_now(self) -> datetime:
        return self.now(UTC)

    def local_now(self):
        return self.now(self.local_tz)

    @property
    def local_tz(self) -> tzinfo:
        info = self.now().astimezone().tzinfo
        assert info
        return info

    def today_start_local(self) -> datetime:
        return self.now(self.local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

    def today_start_utc(self) -> datetime:
        return self.today_start_local().astimezone(UTC)

    def db_time_to_local(self, dt: datetime) -> datetime:
        return dt.replace(tzinfo=UTC).astimezone(self.local_tz)


class FakeClock(Clock):  # noqa
    def __init__(self, now: datetime):
        self._now = now

    def now(self):
        return self._now


get_utc_now = lambda: datetime.now(UTC)


def string_to_timedelta(time_to_completion: str) -> timedelta:
    # validate that the time_to_completion is in the form of NUMBER TIME_UNIT
    # where TIME_UNIT is one of HOUR, DAY, WEEK, MONTH
    # return the timedelta

    logger.debug("Converting time to completion string to timedelta: '%s'", time_to_completion)

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


def ensure_utc(dt: datetime) -> datetime:
    """Convert a datetime object to UTC if it contains time; leave date-only as naive."""
    if dt.tzinfo is None:
        return pytz.utc.localize(dt)
    else:
        return dt.astimezone(pytz.UTC)
