from datetime import datetime, timedelta, tzinfo

import pytz
from pytz import UTC

from ..core.logging import get_logger

logger = get_logger()


def local_now() -> datetime:
    return datetime.now(local_tz())


def local_tz() -> tzinfo:
    info = datetime.now().astimezone().tzinfo
    assert info
    return info


def today_start_local() -> datetime:
    return local_now().replace(hour=0, minute=0, second=0, microsecond=0)


def today_start_utc() -> datetime:
    return today_start_local().astimezone(UTC)


def db_time_to_local(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC).astimezone(local_tz())


def utc_now():
    return datetime.now(UTC)


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


def string_to_datetime(date_string: str) -> datetime:
    """Convert a date/time string to a UTC datetime object.

    Supports formats:
    - "YYYY-MM-DD HH:MM" (e.g., "2024-12-25 09:00")
    - "YYYY-MM-DD HH:MM:SS" (e.g., "2024-12-25 09:00:00")
    - "YYYY-MM-DD" (defaults to 00:00:00)

    Args:
        date_string (str): The date/time string to parse

    Returns:
        datetime: A UTC datetime object

    Raises:
        ValueError: If the date string format is invalid
    """
    date_string = date_string.strip()

    # Try different datetime formats
    formats = [
        "%Y-%m-%d %H:%M:%S",  # 2024-12-25 09:00:00
        "%Y-%m-%d %H:%M",  # 2024-12-25 09:00
        "%Y-%m-%d",  # 2024-12-25
    ]

    for fmt in formats:
        try:
            # Parse as naive datetime first
            naive_dt = datetime.strptime(date_string, fmt)
            # Assume input is in local timezone, then convert to UTC
            local_dt = naive_dt.replace(tzinfo=local_tz())
            return local_dt.astimezone(UTC)
        except ValueError:
            continue

    # If none of the formats worked, raise an error
    raise ValueError(
        f"Invalid datetime format: '{date_string}'. Expected formats: 'YYYY-MM-DD HH:MM:SS', 'YYYY-MM-DD HH:MM', or 'YYYY-MM-DD'"
    )
