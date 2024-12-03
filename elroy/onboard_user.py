import asyncio

from sqlmodel import Session

from .config.config import ChatModel, ElroyConfig
from .io.base import ElroyIO
from .io.cli import CliIO
from .llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from .messaging.context import get_refreshed_system_message
from .repository.data_models import SYSTEM, ContextMessage
from .repository.goals.operations import create_onboarding_goal
from .repository.message import db_replace_context_messages
from .repository.user import create_user, get_user_id_if_exist
from .tools.user_preferences import db_set_user_preferred_name


def get_or_create_user(session: Session, io: ElroyIO, config: ElroyConfig, token: str) -> int:
    user_id = get_user_id_if_exist(session, token)

    if user_id:
        return user_id

    else:
        user_id = create_user(session, token)

        if isinstance(io, CliIO):
            return asyncio.run(onboard_user(session, config.chat_model, io, user_id))
        else:
            raise NotImplementedError


async def onboard_user(
    session: Session,
    chat_model: ChatModel,
    io: CliIO,
    user_id: int,
):
    preferred_name = await io.prompt_user("Welcome to Elroy! What should I call you?")
    db_set_user_preferred_name(session, user_id, preferred_name)

    create_onboarding_goal(session, user_id, preferred_name)

    db_replace_context_messages(
        session,
        user_id,
        [
            get_refreshed_system_message(chat_model, preferred_name, []),
            ContextMessage(
                role=SYSTEM,
                content=ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT(preferred_name),
                chat_model=None,
            ),
        ],
    )

    return user_id
