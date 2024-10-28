from sqlmodel import Session

from elroy.config import ElroyConfig, ElroyContext
from elroy.io.base import ElroyIO
from elroy.onboard_user import onboard_user
from tests.utils import process_test_message

BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME = "Remember to follow through on basketball shots"


def create_test_user(session: Session, io: ElroyIO, elroy_config: ElroyConfig, initial_messages=[]) -> int:
    """
    Returns:
        int: The ID of the created user.
    """
    user_id = onboard_user(session, io, elroy_config, "Test User")

    context = ElroyContext(
        session=session,
        user_id=user_id,
        io=io,
        config=elroy_config,
    )

    for message in initial_messages:
        process_test_message(context, message)
    return user_id
