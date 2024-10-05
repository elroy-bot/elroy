import pytz
from sqlmodel import Session
from toolz import pipe
from toolz.curried import map

from elroy.system.parameters import UNKNOWN


def set_display_internal_monologue(session: Session, user_id: int, should_display: bool) -> str:
    """Sets whether the assistant should display its internal monologue.

    Args:
        user_id (int): user id
        should_display (bool): Whether the assistant should display its internal monologue.

    Returns:
        str: Confirmation message.
    """

    user_preference = _get_user_preference(session, user_id)

    old_preference = user_preference.display_internal_monologue or False

    user_preference.display_internal_monologue = should_display
    session.commit()

    return f"Display internal monologue set to {should_display}. Previous value was {old_preference}."


def get_display_internal_monologue(session: Session, user_id: int) -> bool:
    """Gets whether the assistant should display its internal monologue.

    Args:
        user_id (int): user id

    Returns:
        bool: Whether the assistant should display its internal monologue.
    """
    user_preference = _get_user_preference(session, user_id)

    return user_preference.display_internal_monologue or False


def set_user_time_zone(session: Session, user_id: int, time_zone: str) -> None:
    """
    Set the user's time zone.

    Args:
        user_id: The user's ID.
        time_zone: The user's time zone. Should be a string included in pytz.all_timezones.
    """

    user_preference = _get_user_preference(session, user_id)

    # check if valid time zone
    if time_zone not in pytz.all_timezones:
        raise ValueError(f"Invalid time zone: {time_zone}. Valid list should be in pytz.all_timezones")

    user_preference.user_time_zone = time_zone
    session.commit()


def print_context_messages(session: Session, user_id: int) -> str:
    """Logs all of the current context messages to stdout

    Args:
        session (Session): _description_
        user_id (int): _description_
    """

    from elroy.store.message import get_context_messages

    return pipe(
        get_context_messages(session, user_id), map(lambda x: f"{x.role} ({x.memory_metadata}): {x.content}"), list, "-----\n".join, str
    )  # type: ignore


def set_user_preferred_name(session: Session, user_id: int, preferred_name: str) -> None:
    """
    Set the user's preferred name.

    Args:
        user_id: The user's ID.
        preferred_name: The user's preferred name.
    """

    user_preference = _get_user_preference(session, user_id)

    user_preference.preferred_name = preferred_name
    session.commit()


def get_user_time_zone(session: Session, user_id: int) -> str:
    """Returns the user's time zone.

    Args:
        user_id (int): the user ID

    Returns:
        str: String representing the user's time zone.
    """

    user_preference = _get_user_preference(session, user_id)

    return user_preference.user_time_zone or UNKNOWN


def get_user_preferred_name(session: Session, user_id: int) -> str:
    """Returns the user's preferred name.

    Args:
        user_id (int): the user ID

    Returns:
        str: String representing the user's preferred name.
    """

    user_preference = _get_user_preference(session, user_id)

    return user_preference.preferred_name or UNKNOWN


def set_user_full_name(session: Session, user_id: int, full_name: str) -> str:
    """Sets the user's full name.

    Args:
        user_id (int): user id
        full_name (str): The full name of the user

    Returns:
        str: result of the attempt to set the user's full name
    """

    user_preference = _get_user_preference(session, user_id)

    old_full_name = user_preference.full_name or UNKNOWN
    user_preference.full_name = full_name
    session.commit()

    return f"Full name set to {full_name}. Previous value was {old_full_name}."


def get_user_full_name(session: Session, user_id: int) -> str:
    """Returns the user's full name.

    Args:
        user_id (int): the user ID

    Returns:
        str: String representing the user's full name.
    """

    user_preference = _get_user_preference(session, user_id)

    return user_preference.full_name or "Unknown name"


def _get_user_preference(session: Session, user_id: int):
    from sqlmodel import select

    from elroy.store.user import UserPreference

    user_preference = session.exec(select(UserPreference).where(UserPreference.user_id == user_id, UserPreference.is_active == True)).first()  # type: ignore

    if user_preference is None:
        user_preference = UserPreference(user_id=user_id, is_active=True)
        session.add(user_preference)
        session.commit()
        session.refresh(user_preference)
    return user_preference
