from rich.console import Console
from sqlmodel import Session

from elroy.config import ElroyContext
from elroy.onboard_user import onboard_user
from elroy.tools.messenger import process_message

BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME = "Remember to follow through on basketball shots"


def create_test_user(session: Session, console: Console, initial_messages=[]) -> int:
    """
    Returns:
        int: The ID of the created user.
    """
    user_id = onboard_user(session, "Test User")

    context = ElroyContext(
        session=session,
        user_id=user_id,
        console=console,
    )

    for message in initial_messages:
        process_message(context, message)
    return user_id
