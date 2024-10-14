from rich.console import Console
from sqlmodel import Session

from elroy.config import ElroyContext
from elroy.llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from elroy.memory.system_context import get_refreshed_system_message
from elroy.store.data_models import ContextMessage
from elroy.store.goals import create_onboarding_goal
from elroy.store.message import replace_context_messages
from elroy.store.user import create_user


def onboard_user(session: Session, preferred_name: str) -> int:
    user_id = create_user(session)

    assert isinstance(user_id, int)

    context = ElroyContext(
        session=session,
        user_id=user_id,
        console=Console(),
    )

    create_onboarding_goal(context, preferred_name)

    replace_context_messages(
        context,
        [
            get_refreshed_system_message(preferred_name, []),
            ContextMessage(role="system", content=ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT(preferred_name)),
        ],
    )
    from elroy.system.watermark import set_context_watermark_seconds

    set_context_watermark_seconds(user_id)

    return user_id


if __name__ == "__main__":
    pass
