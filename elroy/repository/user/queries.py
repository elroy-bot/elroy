from sqlmodel import Session, select

from ...config.personas import PERSONA
from ...core.constants import (
    ASSISTANT_ALIAS_STRING,
    DEFAULT_USER_NAME,
    USER_ALIAS_STRING,
)
from ...db.db_models import User
from .session import UserRuntime, UserSession
from .store import UserPreferenceStore, do_get_or_create_user_preference


def get_assistant_name(user_session: UserSession, runtime: UserRuntime) -> str:
    user_preference = UserPreferenceStore(user_session.db, user_session.user_id).get_or_create_user_preference()
    if user_preference.assistant_name:
        return user_preference.assistant_name
    return runtime.default_assistant_name


def do_get_assistant_name(session: Session, user_id: int) -> str:
    user_preference = do_get_or_create_user_preference(session, user_id)
    if user_preference.assistant_name:
        return user_preference.assistant_name
    return "ASSISTANT"  # This is inconsistent if there's a config value for default_assistant_name, consider updating


def get_persona(user_session: UserSession, runtime: UserRuntime):
    """Get the persona for the user, or the default persona if the user has not set one.

    Returns:
        str: The text of the persona.

    """
    user_preference = UserPreferenceStore(user_session.db, user_session.user_id).get_or_create_user_preference()
    raw_persona = user_preference.system_persona or PERSONA

    user_noun = user_preference.preferred_name or "my user"
    return raw_persona.replace(USER_ALIAS_STRING, user_noun).replace(ASSISTANT_ALIAS_STRING, get_assistant_name(user_session, runtime))


def is_user_exists(session: Session, user_token: str) -> bool:
    return bool(session.exec(select(User).where(User.token == user_token)).first())


def do_get_user_preferred_name(session: Session, user_id: int) -> str:
    user_preference = do_get_or_create_user_preference(session, user_id)

    return user_preference.preferred_name or DEFAULT_USER_NAME
