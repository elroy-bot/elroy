from ...core.constants import DEFAULT_USER_NAME, tool
from ...core.turn import TurnContext
from .factory import (
    build_user_preference_orchestrator,
    build_user_preference_store,
)
from .queries import do_get_user_preferred_name
from .session import build_user_session


@tool
def set_assistant_name(turn: TurnContext, assistant_name: str) -> str:
    """Sets the assistant name for the user."""
    return build_user_preference_orchestrator(turn).set_assistant_name(assistant_name)


def reset_system_persona(turn: TurnContext) -> str:
    return build_user_preference_orchestrator(turn).reset_system_persona()


def set_persona(turn: TurnContext, system_persona: str) -> str:
    return build_user_preference_orchestrator(turn).set_persona(system_persona)


@tool
def set_user_full_name(turn: TurnContext, full_name: str, override_existing: bool | None = False) -> str:
    """Sets the user's full name.

    Guidance for usage:
    - Should predominantly be used relatively in the user journey. However, ensure to not be pushy in getting personal information early.
    - For existing users, this should be used relatively rarely.

    Args:
        full_name: The full name of the user
        override_existing: Whether to override an existing full name, if it is already set. Override existing should only be used if a known full name has been found to be incorrect.

    Returns:
        str: Result of the attempt to set the user's full name
    """
    user_session = build_user_session(turn)
    user_preference = build_user_preference_store(user_session).get_or_create_user_preference()

    old_full_name = user_preference.full_name or DEFAULT_USER_NAME
    if old_full_name != DEFAULT_USER_NAME and not override_existing:
        return f"Full name already set to {user_preference.full_name}. If this should be changed, set override_existing=True."
    user_preference.full_name = full_name
    user_session.db.commit()

    return f"Full name set to {full_name}. Previous value was {old_full_name}."


@tool
def set_user_preferred_name(turn: TurnContext, preferred_name: str, override_existing: bool | None = False) -> str:
    """
    Set the user's preferred name. Should predominantly be used relatively early in first conversations, and relatively rarely afterward.

    Args:
        preferred_name: The user's preferred name.
        override_existing: Whether to override an existing preferred name, if it is already set. Override existing should only be used if a known preferred name has been found to be incorrect.
    """
    user_session = build_user_session(turn)
    user_preference = build_user_preference_store(user_session).get_or_create_user_preference()

    old_preferred_name = user_preference.preferred_name or DEFAULT_USER_NAME

    if old_preferred_name != DEFAULT_USER_NAME and not override_existing:
        return f"Preferred name already set to {user_preference.preferred_name}. If this should be changed, use override_existing=True."
    user_preference.preferred_name = preferred_name

    user_session.db.commit()
    return f"Set user preferred name to {preferred_name}. Was {old_preferred_name}."


@tool
def get_user_full_name(turn: TurnContext) -> str:
    """Returns the user's full name.

    Returns:
        str: String representing the user's full name.
    """
    user_session = build_user_session(turn)
    user_preference = build_user_preference_store(user_session).get_or_create_user_preference()

    return user_preference.full_name or "Unknown name"


@tool
def get_user_preferred_name(turn: TurnContext) -> str:
    """Returns the user's preferred name.

    Returns:
        str: String representing the user's preferred name.
    """
    user_session = build_user_session(turn)
    return do_get_user_preferred_name(user_session.db.session, user_session.user_id)
