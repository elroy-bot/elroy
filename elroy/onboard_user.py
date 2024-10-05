import re

from sqlmodel import Session

from elroy.llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from elroy.memory.system_context import get_refreshed_system_message
from elroy.store.goals import create_onboarding_goal
from elroy.store.message import ContextMessage, replace_context_messages
from elroy.store.user import create_user, get_user_id_by_phone
from elroy.system.parameters import UNKNOWN


def onboard_user(session: Session, input_phone: str) -> int:
    phone = input_phone.replace("whatsapp:", "")

    # Validate E.164 format
    if not _validate_e164(phone):
        raise ValueError(f"Invalid phone number format. Please provide a number in E.164 format (e.g., +12345678901)")

    # Check for existing user
    try:
        existing_user = get_user_id_by_phone(session, phone)
        if existing_user:
            raise ValueError(f"User with phone {phone} already exists")
    except KeyError:
        pass  # expected

    user_id = create_user(session, phone)

    assert isinstance(user_id, int)

    create_onboarding_goal(session, user_id)

    replace_context_messages(
        session,
        user_id,
        [
            get_refreshed_system_message(UNKNOWN, []),
            ContextMessage(role="system", content=ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT),
        ],
    )
    from elroy.system.watermark import set_context_watermark_seconds

    set_context_watermark_seconds(user_id)

    return user_id


def _validate_e164(phone: str) -> bool:
    """Validate if the phone number is in E.164 format."""
    pattern = r"^\+[1-9]\d{1,14}$"
    return bool(re.match(pattern, phone))


if __name__ == "__main__":
    pass
