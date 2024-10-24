import logging
from datetime import datetime, timedelta

from pytz import UTC


get_utc_now = lambda: datetime.now(UTC)


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
