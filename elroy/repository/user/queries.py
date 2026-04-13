from sqlmodel import Session, select

from ...core.constants import (
    ASSISTANT_ALIAS_STRING,
    DEFAULT_USER_NAME,
    USER_ALIAS_STRING,
)
from ...core.ctx import ElroyContext
from ...db.db_models import User
from ...db.db_session import DbSession
from .operations import do_get_or_create_user_preference


def assistant_name_for_user(session: Session, user_id: int, default_assistant_name: str) -> str:
    user_preference = do_get_or_create_user_preference(session, user_id)
    if user_preference.assistant_name:
        return user_preference.assistant_name
    return default_assistant_name


def get_assistant_name(ctx: ElroyContext) -> str:
    if not ctx.user_id:
        return ctx.default_assistant_name
    return assistant_name_for_user(ctx.db.session, ctx.user_id, ctx.default_assistant_name)


def do_get_assistant_name(session: Session, user_id: int) -> str:
    return assistant_name_for_user(session, user_id, "ASSISTANT")


def persona_for_user(session: Session, user_id: int, default_persona: str | None, default_assistant_name: str) -> str:
    user_preference = do_get_or_create_user_preference(session, user_id)
    raw_persona = user_preference.system_persona or default_persona or ""
    user_noun = user_preference.preferred_name or "my user"
    assistant_name = assistant_name_for_user(session, user_id, default_assistant_name)
    return raw_persona.replace(USER_ALIAS_STRING, user_noun).replace(ASSISTANT_ALIAS_STRING, assistant_name)


def get_persona(ctx: ElroyContext):
    """Get the persona for the user, or the default persona if the user has not set one.

    Returns:
        str: The text of the persona.

    """
    return persona_for_user(ctx.db.session, ctx.user_id, ctx.default_persona, ctx.default_assistant_name)


def get_user_id_if_exists(db: DbSession, user_token: str) -> int | None:
    user = db.exec(select(User).where(User.token == user_token)).first()
    if user:
        id = user.id
        assert id
        return id
    return None


def is_user_exists(session: Session, user_token: str) -> bool:
    return bool(session.exec(select(User).where(User.token == user_token)).first())


def do_get_user_preferred_name(session: Session, user_id: int) -> str:
    user_preference = do_get_or_create_user_preference(session, user_id)

    return user_preference.preferred_name or DEFAULT_USER_NAME
