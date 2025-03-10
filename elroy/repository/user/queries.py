from typing import Optional

from sqlmodel import Session, select

from ...config.constants import ASSISTANT_ALIAS_STRING, UNKNOWN, USER_ALIAS_STRING
from ...config.ctx import ElroyContext
from ...db.db_models import User
from ...db.db_session import DbSession
from .operations import do_get_or_create_user_preference, get_or_create_user_preference


def get_assistant_name(ctx: ElroyContext) -> str:
    if not ctx.user_id:
        return ctx.default_assistant_name
    else:
        user_preference = get_or_create_user_preference(ctx)
        if user_preference.assistant_name:
            return user_preference.assistant_name
        else:
            return ctx.default_assistant_name


def do_get_assistant_name(session: Session, user_id: int) -> str:
    user_preference = do_get_or_create_user_preference(session, user_id)
    if user_preference.assistant_name:
        return user_preference.assistant_name
    else:
        return "ASSISTANT"  # TODO: this is inconsistent if there's a config value for default_assistant_name


def get_persona(ctx: ElroyContext):
    """Get the persona for the user, or the default persona if the user has not set one.

    Returns:
        str: The text of the persona.

    """
    user_preference = get_or_create_user_preference(ctx)
    if user_preference.system_persona:
        raw_persona = user_preference.system_persona
    else:
        raw_persona = ctx.default_persona

    if user_preference.preferred_name:
        user_noun = user_preference.preferred_name
    else:
        user_noun = "my user"
    return raw_persona.replace(USER_ALIAS_STRING, user_noun).replace(ASSISTANT_ALIAS_STRING, get_assistant_name(ctx))


def get_user_id_if_exists(db: DbSession, user_token: str) -> Optional[int]:
    user = db.exec(select(User).where(User.token == user_token)).first()
    if user:
        id = user.id
        assert id
        return id


def is_user_exists(session: Session, user_token: str) -> bool:
    return bool(session.exec(select(User).where(User.token == user_token)).first())


def do_get_user_preferred_name(session: Session, user_id: int) -> str:
    user_preference = do_get_or_create_user_preference(session, user_id)

    return user_preference.preferred_name or UNKNOWN
