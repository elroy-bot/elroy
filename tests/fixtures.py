from sqlmodel import Session

from elroy.onboard_user import onboard_user
from elroy.tools.messenger import process_message

BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME = "Remember to follow through on basketball shots"


def create_test_user(session: Session, initial_messages=[]) -> int:
    """
    Returns:
        int: The ID of the created user.
    """
    user_id = onboard_user(session, "Test User")

    for message in initial_messages:
        process_message(
            session,
            user_id,
            message,
        )
    return user_id
