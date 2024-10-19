from inspect import signature
from typing import Optional

from sqlmodel import select
from toolz import pipe
from toolz.curried import map

from elroy.config import ElroyContext
from elroy.memory.system_context import format_context_messages
from elroy.store.data_models import ContextMessage, Goal
from elroy.store.goals import (add_goal_status_update, create_goal,
                               delete_goal_permamently, mark_goal_completed,
                               rename_goal)
from elroy.store.message import (add_context_messages, get_context_messages,
                                 get_current_system_message,
                                 replace_context_messages)
from elroy.system.parameters import CHAT_MODEL
from elroy.tools.functions.user_preferences import (get_user_full_name,
                                                    get_user_preferred_name,
                                                    set_user_full_name,
                                                    set_user_preferred_name)


def invoke_system_command(context: ElroyContext, msg: str) -> str:
    if msg.startswith("/"):
        msg = msg[1:]

    command, *args = msg.split(" ")

    func = SYSTEM_COMMANDS.get(command)

    if not func:
        return f"Unknown command: {command}"

    sig = signature(func)
    params = list(sig.parameters.values())

    try:
        func_args = []
        for i, param in enumerate(params):
            if param.annotation == ElroyContext:
                func_args.append(context)
            elif param.annotation == str and i == len(params) - 1:
                # If it's a string parameter and the last one, join remaining args
                func_args.append(" ".join(args[i - 1 :]))
                break
            elif i - 1 < len(args):  # Check if there are still args left
                func_args.append(args[i - 1])
            else:
                # Not enough arguments provided
                return f"Error: Not enough arguments for command {command}"

        return func(*func_args)
    except Exception as e:
        return f"Error invoking system command: {e}"


def refresh_system_instructions(context: ElroyContext) -> str:
    """Refreshes the system instructions

    Args:
        user_id (_type_): user id

    Returns:
        str: The result of the system instruction refresh
    """

    from elroy.memory.system_context import get_refreshed_system_message
    from elroy.store.message import get_context_messages

    context_messages = get_context_messages(context)
    context_messages[0] = get_refreshed_system_message(get_user_preferred_name(context), context_messages[1:])
    replace_context_messages(context, context_messages)
    return "System instruction refresh complete"


def print_system_instruction(context: ElroyContext) -> Optional[str]:
    """Prints the current system instruction for the assistant

    Args:
        user_id (int): user id

    Returns:
        str: The current system instruction
    """

    return pipe(
        get_current_system_message(context),
        lambda _: _.content if _ else None,
    )  # type: ignore


def print_available_commands(context: ElroyContext) -> str:
    """Prints the available system commands

    Returns:
        str: The available system commands
    """

    return "Available commands: " + "\n".join(SYSTEM_COMMANDS.keys())


def reset_system_context(context: ElroyContext) -> str:
    """Resets the context for the user, removing all messages from the context except the system message.
    This should be used sparingly, only at the direct request of the user.

    Args:
        user_id (int): user id

    Returns:
        str: The result of the context reset
    """

    current_sys_message = get_current_system_message(context)

    if not current_sys_message:
        raise ValueError("No system message found")
    else:
        current_sys_message_id = current_sys_message.id
        assert current_sys_message_id
        replace_context_messages(
            context,
            [current_sys_message],
        )

    return "Context reset complete"


def print_context_messages(context: ElroyContext) -> str:
    """Logs all of the current context messages to stdout

    Args:
        session (Session): _description_
        user_id (int): _description_
    """

    from elroy.store.message import get_context_messages

    return pipe(
        get_context_messages(context),
        map(lambda x: f"{x.role} ({x.memory_metadata}): {x.content}"),
        list,
        "-----\n".join,
        str,
    )  # type: ignore


def print_goal(context: ElroyContext, goal_name: str) -> str:
    """Prints the goal with the given name

    Args:
        context (ElroyContext): context obj
        goal_name (str): Name of the goal

    Returns:
        str: Information for the goal with the given name
    """
    goal = context.session.exec(
        select(Goal).where(
            Goal.user_id == context.user_id,
            Goal.name == goal_name,
            Goal.is_active == True,
        )
    ).first()
    if goal:
        status_string = ("Status:" + "\n".join(goal.status_updates)) if goal.status_updates else ""
        return f"Goal: {goal.name}\n\nDescription: {goal.description}\n{status_string}"
    else:
        return f"Goal '{goal_name}' not found for the current user."


def contemplate(context: ElroyContext) -> str:
    """Contemplate the current context and return a response

    Args:
        context (ElroyContext): context obj

    Returns:
        str: The response to the contemplation
    """
    from elroy.llm.client import query_llm
    from elroy.llm.prompts import contemplate_prompt

    user_preferred_name = get_user_preferred_name(context)
    context_messages = get_context_messages(context)

    msgs_input = format_context_messages(user_preferred_name, context_messages)

    response = query_llm(
        prompt=msgs_input,
        system=contemplate_prompt(user_preferred_name),
        model=CHAT_MODEL,
    )

    add_context_messages(context, [ContextMessage(role="assistant", content=response)])

    context.console.print(response)
    return response


def drop_goal_from_current_context_only(context: ElroyContext, goal_name: str) -> str:
    """Drops the goal with the given name

    Args:
        context (ElroyContext): context obj
        goal_name (str): Name of the goal

    Returns:
        str: Information for the goal with the given name
    """
    from elroy.tools.messenger import remove_goal_from_context

    goal = context.session.exec(
        select(Goal).where(
            Goal.user_id == context.user_id,
            Goal.name == goal_name,
        )
    ).first()
    if goal:
        assert goal.id
        remove_goal_from_context(context, goal.id)
        return f"Goal '{goal_name}' dropped."

    else:
        return f"Goal '{goal_name}' not found for the current user."


ASSISTANT_VISIBLE_COMMANDS = [
    contemplate,
    get_user_full_name,
    set_user_full_name,
    get_user_preferred_name,
    set_user_preferred_name,
    create_goal,
    rename_goal,
    drop_goal_from_current_context_only,
    add_goal_status_update,
    mark_goal_completed,
    delete_goal_permamently,
]

USER_ONLY_COMMANDS = [
    reset_system_context,
    print_context_messages,
    print_goal,
    print_system_instruction,
    refresh_system_instructions,
    print_available_commands,
]


SYSTEM_COMMANDS = {f.__name__: f for f in ASSISTANT_VISIBLE_COMMANDS + USER_ONLY_COMMANDS}
