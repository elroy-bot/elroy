from sqlmodel import Session

from .config.config import ElroyConfig, ElroyContext
from .io.base import ElroyIO
from .llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from .messaging.context import get_refreshed_system_message
from .repository.data_models import ContextMessage
from .repository.goals.operations import create_onboarding_goal
from .repository.message import replace_context_messages
from .repository.user import create_user


def onboard_user(session: Session, io: ElroyIO, config: ElroyConfig, preferred_name: str) -> int:
    user_id = create_user(session)

    assert isinstance(user_id, int)

    context = ElroyContext(session, io, config, user_id)

    create_onboarding_goal(context, preferred_name)

    replace_context_messages(
        context,
        [
            get_refreshed_system_message(preferred_name, []),
            ContextMessage(role="system", content=ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT(preferred_name)),
        ],
    )

    return user_id


if __name__ == "__main__":
    pass
