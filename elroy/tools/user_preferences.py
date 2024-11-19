from typing import Optional

from ..config.config import ElroyContext
from ..config.constants import UNKNOWN
from ..repository.data_models import UserPreference


def set_user_preferred_name(context: ElroyContext, preferred_name: str, override_existing: Optional[bool] = False) -> str:
    """
    Set the user's preferred name. Should predominantly be used relatively early in first conversations, and relatively rarely afterward.

    Args:
        user_id: The user's ID.
        preferred_name: The user's preferred name.
        override_existing: Whether to override the an existing preferred name, if it is already set. Override existing should only be used if a known preferred name has been found to be incorrect.
    """

    user_preference = _get_user_preference(context)

    old_preferred_name = user_preference.preferred_name or UNKNOWN

    if old_preferred_name != UNKNOWN and not override_existing:
        return f"Preferred name already set to {user_preference.preferred_name}. If this should be changed, use override_existing=True."
    else:
        user_preference.preferred_name = preferred_name

        context.session.commit()
        return f"Set user preferred name to {preferred_name}. Was {old_preferred_name}."


def get_user_preferred_name(context: ElroyContext) -> str:
    """Returns the user's preferred name.

    Args:
        user_id (int): the user ID

    Returns:
        str: String representing the user's preferred name.
    """

    user_preference = _get_user_preference(context)

    return user_preference.preferred_name or UNKNOWN


def set_user_full_name(context: ElroyContext, full_name: str, override_existing: Optional[bool] = False) -> str:
    """Sets the user's full name.

    Guidance for usage:
    - Should predominantly be used relatively in the user journey. However, ensure to not be pushy in getting personal information early.
    - For existing users, this should be used relatively rarely.

    Args:
        user_id (int): user id
        full_name (str): The full name of the user
        override_existing (bool): Whether to override the an existing full name, if it is already set. Override existing should only be used if a known full name has been found to be incorrect.

    Returns:
        str: result of the attempt to set the user's full name
    """

    user_preference = _get_user_preference(context)

    old_full_name = user_preference.full_name or UNKNOWN
    if old_full_name != UNKNOWN and not override_existing:
        return f"Full name already set to {user_preference.full_name}. If this should be changed, set override_existing=True."
    else:
        user_preference.full_name = full_name
        context.session.commit()

        return f"Full name set to {full_name}. Previous value was {old_full_name}."


def get_user_full_name(context: ElroyContext) -> str:
    """Returns the user's full name.

    Args:
        user_id (int): the user ID

    Returns:
        str: String representing the user's full name.
    """

    user_preference = _get_user_preference(context)

    return user_preference.full_name or "Unknown name"


def _get_user_preference(context: ElroyContext):
    from sqlmodel import select

    user_preference = context.session.exec(
        select(UserPreference).where(
            UserPreference.user_id == context.user_id,
            UserPreference.is_active == True,
        )
    ).first()

    if user_preference is None:
        user_preference = UserPreference(user_id=context.user_id, is_active=True)
        context.session.add(user_preference)
        context.session.commit()
        context.session.refresh(user_preference)
    return user_preference
