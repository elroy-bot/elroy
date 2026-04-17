from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from sqlmodel import Session, select

from ...core.constants import user_only_tool
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import User, UserPreference
from ...db.db_session import DbSession
from ...utils.utils import is_blank

logger = get_logger()


@dataclass(frozen=True)
class UserPreferenceCallbacks:
    refresh_system_instructions_fn: Callable[[], None]


class UserPreferenceOrchestrator:
    def __init__(self, db: DbSession, user_id: int, callbacks: UserPreferenceCallbacks):
        self.db = db
        self.user_id = user_id
        self.callbacks = callbacks

    def get_or_create_user_preference(self) -> UserPreference:
        return do_get_or_create_user_preference(self.db.session, self.user_id)

    def set_assistant_name(self, assistant_name: str) -> str:
        user_preference = self.get_or_create_user_preference()
        user_preference.assistant_name = assistant_name
        self.db.add(user_preference)
        self.db.commit()
        self.callbacks.refresh_system_instructions_fn()
        return f"Assistant name updated to {assistant_name}."

    def reset_system_persona(self) -> str:
        user_preference = self.get_or_create_user_preference()
        if not user_preference.system_persona:
            logger.warning("System persona was already set to default")

        user_preference.system_persona = None
        self.db.add(user_preference)
        self.db.commit()
        self.callbacks.refresh_system_instructions_fn()
        return "System persona cleared, will now use default persona."

    def set_persona(self, system_persona: str) -> str:
        system_persona = system_persona.strip()
        if is_blank(system_persona):
            raise ValueError("System persona cannot be blank.")

        user_preference = self.get_or_create_user_preference()
        if user_preference.system_persona == system_persona:
            logger.info("New system persona and old system persona are identical")
            return "New system persona and old system persona are identical"

        user_preference.system_persona = system_persona
        self.db.add(user_preference)
        self.db.commit()
        self.callbacks.refresh_system_instructions_fn()
        return "System persona updated."


def create_user_id(db: DbSession, user_token: str) -> int:
    user = db.persist(User(token=user_token))
    user_id = user.id
    assert user_id
    return user_id


def _orchestrator(ctx: ElroyContext) -> UserPreferenceOrchestrator:
    from ..context_messages.operations import refresh_system_instructions

    return UserPreferenceOrchestrator(
        db=ctx.db,
        user_id=ctx.user_id,
        callbacks=UserPreferenceCallbacks(
            refresh_system_instructions_fn=lambda: refresh_system_instructions(ctx),
        ),
    )


def get_or_create_user_preference(ctx: ElroyContext) -> UserPreference:
    return _orchestrator(ctx).get_or_create_user_preference()


def do_get_or_create_user_preference(session: Session, user_id: int) -> UserPreference:
    user_preference = session.exec(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            cast(Any, UserPreference.is_active),
        )
    ).first()

    if user_preference is None:
        user_preference = UserPreference(user_id=user_id, is_active=True)
        session.add(user_preference)
        session.commit()
        session.refresh(user_preference)
    return user_preference


@user_only_tool
def set_assistant_name(ctx: ElroyContext, assistant_name: str) -> str:
    """
    Sets the assistant name for the user
    """
    return _orchestrator(ctx).set_assistant_name(assistant_name)


def reset_system_persona(ctx: ElroyContext) -> str:
    """
    Clears the system instruction for the user
    """
    return _orchestrator(ctx).reset_system_persona()


def set_persona(ctx: ElroyContext, system_persona: str) -> str:
    """
    Sets the system instruction for the user
    """
    return _orchestrator(ctx).set_persona(system_persona)
