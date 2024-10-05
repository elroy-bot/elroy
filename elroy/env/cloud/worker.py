import logging
from typing import Optional, Tuple

from sqlmodel import Session

from elroy.system.rate_limiter import (
    is_within_daily_warning_message_limit,
    is_within_non_premium_daily_message_limit)


def response_to_twilio_message(session: Session, user_id: int, received_msg: str) -> Optional[str]:
    from elroy.tools.messenger import process_message

    is_user_within_limits, warning_msg = _check_for_limits(session, user_id)

    if is_user_within_limits:
        return process_message(session, user_id, received_msg)

    elif warning_msg:
        logging.warning(f"Delivering warning to user {user_id}")
        return process_message(session, user_id, warning_msg)
    else:
        logging.warning(f"Silently dropping message for user {user_id}")


def _check_for_limits(session: Session, user_id: int) -> Tuple[bool, Optional[str]]:
    from elroy.store.user import is_user_premium

    if is_user_premium(session, user_id):
        return True, None
    elif is_within_non_premium_daily_message_limit(user_id):
        return True, None
    else:
        return False, (
            "You have exceeded the daily message limit. Please try again tomorrow."
            if is_within_daily_warning_message_limit(user_id)
            else None
        )
