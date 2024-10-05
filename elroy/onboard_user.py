from sqlmodel import Session

from elroy.llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from elroy.memory.system_context import get_refreshed_system_message
from elroy.store.goals import create_onboarding_goal
from elroy.store.message import ContextMessage, replace_context_messages
from elroy.store.user import create_user
from elroy.system.parameters import UNKNOWN


def onboard_user(session: Session) -> int:
    user_id = create_user(session)

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


if __name__ == "__main__":
    pass
