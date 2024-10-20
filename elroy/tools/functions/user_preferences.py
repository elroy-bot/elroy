from elroy.config import ElroyContext
from elroy.store.data_models import UserPreference
from elroy.system.parameters import UNKNOWN


def set_user_preferred_name(context: ElroyContext, preferred_name: str) -> None:
    """
    Set the user's preferred name.

    Args:
        user_id: The user's ID.
        preferred_name: The user's preferred name.
    """

    user_preference = _get_user_preference(context)

    user_preference.preferred_name = preferred_name
    context.session.commit()


def get_user_preferred_name(context: ElroyContext) -> str:
    """Returns the user's preferred name.

    Args:
        user_id (int): the user ID

    Returns:
        str: String representing the user's preferred name.
    """

    user_preference = _get_user_preference(context)

    return user_preference.preferred_name or UNKNOWN


def set_user_full_name(context: ElroyContext, full_name: str) -> str:
    """Sets the user's full name.

    Args:
        user_id (int): user id
        full_name (str): The full name of the user

    Returns:
        str: result of the attempt to set the user's full name
    """

    user_preference = _get_user_preference(context)

    old_full_name = user_preference.full_name or UNKNOWN
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
