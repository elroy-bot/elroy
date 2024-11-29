import logging
from typing import Callable, List, Optional, Set

from rich.pretty import Pretty
from sqlmodel import select
from toolz import pipe

from .config.config import ElroyContext
from .llm import client
from .llm.prompts import contemplate_prompt
from .messaging.context import (
    add_goal_to_current_context,
    add_memory_to_current_context,
    drop_goal_from_current_context,
    drop_memory_from_current_context,
    format_context_messages,
    get_refreshed_system_message,
)
from .repository.data_models import SYSTEM, ContextMessage, Goal, Memory
from .repository.goals.operations import (
    add_goal_status_update,
    create_goal,
    delete_goal_permanently,
    goal_to_fact,
    mark_goal_completed,
    rename_goal,
)
from .repository.goals.queries import get_active_goals
from .repository.memory import create_memory, memory_to_fact
from .repository.message import (
    add_context_messages,
    get_context_messages,
    get_current_system_message,
    is_system_instruction,
    replace_context_messages,
)
from .tools.developer import (
    create_bug_report,
    print_elroy_config,
    start_aider_session,
    tail_elroy_logs,
)
from .tools.user_preferences import (
    get_user_full_name,
    get_user_preferred_name,
    set_user_full_name,
    set_user_preferred_name,
)


def refresh_system_instructions(context: ElroyContext) -> str:
    """Refreshes the system instructions

    Args:
        user_id (_type_): user id

    Returns:
        str: The result of the system instruction refresh
    """

    context_messages = get_context_messages(context)
    context_messages[0] = get_refreshed_system_message(
        context.config.chat_model,
        get_user_preferred_name(context),
        context_messages[1:],
    )
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

    return "Available commands: " + "\n".join([f.__name__ for f in SYSTEM_COMMANDS])


def add_internal_thought(context: ElroyContext, thought: str) -> str:
    """Inserts internal thought for the assistant. Useful for guiding the assistant's thoughts in a specific direction.

    Args:
        context (ElroyContext): context obj
        thought (str): The thought to add

    Returns:
        str: The result of the internal thought addition
    """

    add_context_messages(
        context,
        [
            ContextMessage(
                role=SYSTEM,
                content=thought,
                chat_model=context.config.chat_model.model,
            )
        ],
    )

    return f"Internal thought added: {thought}"


def reset_system_context(context: ElroyContext) -> str:
    """Resets the context for the user, removing all messages from the context except the system message.
    This should be used sparingly, only at the direct request of the user.

    Args:
        user_id (int): user id

    Returns:
        str: The result of the context reset
    """

    current_sys_message = get_current_system_message(context)

    if not is_system_instruction(current_sys_message):
        logging.warning(
            f"Current first message is not a system message: " + f"has role {current_sys_message.role}"
            if current_sys_message
            else "No first message found"
        )
        current_sys_message = get_refreshed_system_message(
            context.config.chat_model,
            get_user_preferred_name(context),
            get_context_messages(context),
        )

    replace_context_messages(
        context,
        [current_sys_message],  # type: ignore
    )

    return "Context reset complete"


def print_context_messages(context: ElroyContext) -> Pretty:
    """Logs all of the current context messages to stdout

    Args:
        session (Session): _description_
        user_id (int): _description_
    """

    return Pretty(get_context_messages(context))


def print_goal(context: ElroyContext, goal_name: str) -> str:
    """Prints the goal with the given name. This does NOT create a goal, it only prints the existing goal with the given name if it has been created already.

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
        return goal_to_fact(goal)
    else:
        return f"Goal '{goal_name}' not found for the current user."


def get_active_goal_names(context: ElroyContext) -> List[str]:

    return [goal.name for goal in get_active_goals(context)]


def print_memory(context: ElroyContext, memory_name: str) -> str:
    """Prints the memory with the given name

    Args:
        context (ElroyContext): context obj
        memory_name (str): Name of the memory

    Returns:
        str: Information for the memory with the given name
    """
    memory = context.session.exec(
        select(Memory).where(
            Memory.user_id == context.user_id,
            Memory.name == memory_name,
            Memory.is_active == True,
        )
    ).first()
    if memory:
        return memory_to_fact(memory)
    else:
        return f"Memory '{memory_name}' not found for the current user."


def contemplate(context: ElroyContext, contemplation_prompt: Optional[str] = None) -> str:
    """Contemplate the current context and return a response

    Args:
        context (ElroyContext): context obj
        contemplation_prompt (str, optional): The prompt to contemplate. Can be about the immediate conversation or a general topic. Default wil be a prompt about the current conversation.

    Returns:
        str: The response to the contemplation
    """

    logging.info("Contemplating...")

    user_preferred_name = get_user_preferred_name(context)
    context_messages = get_context_messages(context)

    msgs_input = format_context_messages(user_preferred_name, context_messages)

    response = client.query_llm(
        prompt=msgs_input,
        system=contemplate_prompt(user_preferred_name, contemplation_prompt),
        model=context.config.chat_model,
    )

    add_context_messages(
        context,
        [
            ContextMessage(
                role=SYSTEM,
                content=response,
                chat_model=context.config.chat_model.model,
            )
        ],
    )

    context.io.internal_thought_msg(response)

    return response


IN_CONTEXT_GOAL_COMMANDS: Set[Callable] = {
    drop_goal_from_current_context,
}

NON_CONTEXT_GOAL_COMMANDS: Set[Callable] = {
    add_goal_to_current_context,
}

ALL_ACTIVE_GOAL_COMMANDS: Set[Callable] = {
    rename_goal,
    print_goal,
    add_goal_status_update,
    mark_goal_completed,
    delete_goal_permanently,
}

IN_CONTEXT_MEMORY_COMMANDS: Set[Callable] = {
    drop_memory_from_current_context,
}

NON_CONTEXT_MEMORY_COMMANDS: Set[Callable] = {
    add_memory_to_current_context,
}

ALL_ACTIVE_MEMORY_COMMANDS: Set[Callable] = {
    print_memory,
}

NON_ARG_PREFILL_COMMANDS = {
    create_goal,
    create_memory,
    contemplate,
    start_aider_session,
    get_user_full_name,
    set_user_full_name,
    get_user_preferred_name,
    set_user_preferred_name,
    tail_elroy_logs,
    print_elroy_config,
}

# These are commands that are visible to the assistant to be executed as tools.
ASSISTANT_VISIBLE_COMMANDS = (
    NON_ARG_PREFILL_COMMANDS
    | IN_CONTEXT_GOAL_COMMANDS
    | NON_CONTEXT_GOAL_COMMANDS
    | ALL_ACTIVE_GOAL_COMMANDS
    | IN_CONTEXT_MEMORY_COMMANDS
    | NON_CONTEXT_MEMORY_COMMANDS
    | ALL_ACTIVE_MEMORY_COMMANDS
)


# User only commands are commands that are only available to the user, via CLI.
USER_ONLY_COMMANDS = {
    add_internal_thought,
    reset_system_context,
    print_context_messages,
    print_system_instruction,
    refresh_system_instructions,
    print_available_commands,
    create_bug_report,
}


SYSTEM_COMMANDS = ASSISTANT_VISIBLE_COMMANDS | USER_ONLY_COMMANDS
