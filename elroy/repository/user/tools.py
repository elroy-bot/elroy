from ...core.constants import DEFAULT_USER_NAME, tool
from ...core.ctx import ElroyContext
from .operations import get_or_create_user_preference
from .queries import do_get_user_preferred_name


@tool
def set_user_full_name(ctx: ElroyContext, full_name: str, override_existing: bool | None = False) -> str:
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

    user_preference = get_or_create_user_preference(ctx)

    old_full_name = user_preference.full_name or DEFAULT_USER_NAME
    if old_full_name != DEFAULT_USER_NAME and not override_existing:
        return f"Full name already set to {user_preference.full_name}. If this should be changed, set override_existing=True."
    else:
        user_preference.full_name = full_name
        ctx.db.commit()

        return f"Full name set to {full_name}. Previous value was {old_full_name}."


@tool
def set_user_preferred_name(ctx: ElroyContext, preferred_name: str, override_existing: bool | None = False) -> str:
    """
    Set the user's preferred name. Should predominantly be used relatively early in first conversations, and relatively rarely afterward.

    Args:
        preferred_name: The user's preferred name.
        override_existing: Whether to override an existing preferred name, if it is already set. Override existing should only be used if a known preferred name has been found to be incorrect.
    """

    user_preference = get_or_create_user_preference(ctx)

    old_preferred_name = user_preference.preferred_name or DEFAULT_USER_NAME

    if old_preferred_name != DEFAULT_USER_NAME and not override_existing:
        return f"Preferred name already set to {user_preference.preferred_name}. If this should be changed, use override_existing=True."
    else:
        user_preference.preferred_name = preferred_name

        ctx.db.commit()
        return f"Set user preferred name to {preferred_name}. Was {old_preferred_name}."


@tool
def get_user_full_name(ctx: ElroyContext) -> str:
    """Returns the user's full name.

    Returns:
        str: String representing the user's full name.
    """

    user_preference = get_or_create_user_preference(ctx)

    return user_preference.full_name or "Unknown name"


@tool
def get_user_preferred_name(ctx: ElroyContext) -> str:
    """Returns the user's preferred name.

    Returns:
        str: String representing the user's preferred name.
    """

    return do_get_user_preferred_name(ctx.db.session, ctx.user_id)
