from typing import Optional

from sqlmodel import Session
from toolz import pipe

from elroy.memory.system_context import get_refreshed_system_message
from elroy.store.message import (get_current_system_message,
                                 replace_context_messages)
from elroy.tools.functions.user_preferences import (
    get_display_internal_monologue, get_user_full_name,
    get_user_preferred_name, get_user_time_zone, print_context_messages,
    set_display_internal_monologue, set_user_full_name,
    set_user_preferred_name, set_user_time_zone)


def is_system_command(msg: str) -> bool:
    return msg.split(" ")[0] in SYSTEM_COMMANDS.keys()


def invoke_system_command(session: Session, user_id: int, msg: str) -> str:
    command, *args = msg.split(" ")
    try:
        return SYSTEM_COMMANDS[command](session, user_id, *args)
    except Exception as e:
        return f"Error invoking system command: {e}"


def refresh_system_instructions(session: Session, user_id) -> str:
    """Refreshes the system instructions

    Args:
        user_id (_type_): user id

    Returns:
        str: The result of the system instruction refresh
    """

    from elroy.store.message import get_context_messages

    context_messages = get_context_messages(session, user_id)
    context_messages[0] = get_refreshed_system_message(get_user_preferred_name(session, user_id), context_messages[1:])
    replace_context_messages(session, user_id, context_messages)
    return "System instruction refresh complete"


def print_system_instruction(session: Session, user_id: int) -> Optional[str]:
    """Prints the current system instruction for the assistant

    Args:
        user_id (int): user id

    Returns:
        str: The current system instruction
    """

    return pipe(
        get_current_system_message(session, user_id),
        lambda _: _.content if _ else None,
    )  # type: ignore


def print_available_commands() -> str:
    """Prints the available system commands

    Returns:
        str: The available system commands
    """

    return "Available commands: " + "\n".join(SYSTEM_COMMANDS.keys())


def reset_system_context(session: Session, user_id: int) -> str:
    """Resets the context for the user, removing all messages from the context except the system message.
    This should be used sparingly, only at the direct request of the user.

    Args:
        user_id (int): user id

    Returns:
        str: The result of the context reset
    """

    current_sys_message = get_current_system_message(session, user_id)

    if not current_sys_message:
        raise ValueError("No system message found")
    else:
        current_sys_message_id = current_sys_message.id
        assert current_sys_message_id
        replace_context_messages(
            session,
            user_id,
            [current_sys_message],
        )

    return "Context reset complete"


SYSTEM_COMMANDS = {
    f.__name__.upper(): f
    for f in [
        print_system_instruction,
        set_display_internal_monologue,
        get_display_internal_monologue,
        refresh_system_instructions,
        print_available_commands,
        set_user_time_zone,
        get_user_time_zone,
        set_user_preferred_name,
        get_user_preferred_name,
        set_user_full_name,
        get_user_full_name,
        reset_system_context,
        print_context_messages,
    ]
}
