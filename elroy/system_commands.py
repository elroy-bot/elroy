import logging
import os
import pty
import subprocess
import sys
import termios
import time
import tty
from inspect import signature
from typing import Callable, List, Optional, Set

from rich.pretty import Pretty
from sqlmodel import select
from toolz import pipe
from toolz.curried import filter

from .config.config import ElroyContext
from .config.constants import CHAT_MODEL
from .llm import client
from .llm.prompts import contemplate_prompt
from .messaging.context import (
    add_goal_to_current_context,
    drop_goal_from_current_context_only,
    format_context_messages,
    get_refreshed_system_message,
)
from .repository.data_models import SYSTEM, ContextMessage, Goal, Memory
from .repository.goals.operations import (
    add_goal_status_update,
    create_goal,
    delete_goal_permamently,
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
    replace_context_messages,
)
from .tools.user_preferences import (
    get_user_full_name,
    get_user_preferred_name,
    set_user_full_name,
    set_user_preferred_name,
)
from .utils.ops import experimental


def invoke_system_command(context: ElroyContext, msg: str) -> str:
    """
    Takes user input and executes a system command

    Currently only works well for commands that take 1 non-context argument

    In the future, the execute system command should surface a form
    """
    if msg.startswith("/"):
        msg = msg[1:]

    command, *args = msg.split(" ")

    func = next((f for f in SYSTEM_COMMANDS if f.__name__ == command), None)

    if not func:
        return f"Unknown command: {command}"

    sig = signature(func)
    params = list(sig.parameters.values())

    try:
        func_args = []
        num_required_args = len([p for p in params if p.default is p.empty])

        for i, param in enumerate(params):
            if param.annotation == ElroyContext:
                func_args.append(context)
                continue

            if i < len(args):  # We have an argument provided
                if param.annotation == str and i == num_required_args - 1:
                    # Last *required* string param gets remaining args
                    func_args.append(
                        " ".join(args[i - 1 :])
                    )  # we append i - i because we have already included the context as the first argument.
                    break
                else:
                    func_args.append(args[i])
            elif param.default is not param.empty:
                # Use default value for optional parameter
                continue
            else:
                # Missing required argument
                return f"Error: Missing required argument '{param.name}' for command {command}. Required args: {num_required_args}"

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

    return "Available commands: " + "\n".join([f.__name__ for f in SYSTEM_COMMANDS])


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
        model=CHAT_MODEL,
    )

    add_context_messages(context, [ContextMessage(role=SYSTEM, content=response)])

    context.io.internal_thought_msg(response)

    return response


@experimental
def start_aider_session(context: ElroyContext, file_location: str = ".", comment: str = "") -> str:
    """
    Starts an aider session using a pseudo-terminal, taking over the screen.

    Args:
        context (ElroyContext): The Elroy context object.
        file_location (str): The file or directory location to start aider with. Defaults to current directory.
        comment (str): Initial text to be processed by aider as if it was typed. Defaults to empty string.

    Returns:
        str: A message indicating the result of the aider session start attempt.
    """

    try:
        # Ensure the file_location is an absolute path
        abs_file_location = os.path.abspath(file_location)

        # Determine the directory to change to
        if os.path.isfile(abs_file_location):
            change_dir = os.path.dirname(abs_file_location)
        else:
            change_dir = abs_file_location

        # Prepend /ask so the AI does not immediately start writing code.
        aider_context = (
            "{\n/ask "
            + client.query_llm(
                system="Your task is to provide context to a coding assistant AI. "
                "Given information about a conversation, return information about what the goal is, what the user needs help with, and/or any approaches that have been discussed. "
                "Focus your prompt specifically on what the coding Assistant needs to know. Do not include information about Elroy, personal information about the user, "
                "or anything that isn't relevant to what code the coding assistant will need to write.",
                prompt=pipe(
                    [
                        f"# Aider session file location: {abs_file_location}",
                        "# Comment: {comment}" if comment else None,
                        f"# Chat transcript: {print_context_messages(context)}",
                    ],
                    filter(lambda x: x is not None),
                    list,
                    "\n\n".join,
                ),  # type: ignore
            )
            + "\n}"
        )

        # Print debug information
        print(f"Starting aider session for location: {abs_file_location}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Changing directory to: {change_dir}")

        # Save the current terminal settings
        old_tty = termios.tcgetattr(sys.stdin)

        try:
            # Create a pseudo-terminal
            master_fd, slave_fd = pty.openpty()

            # Change the working directory
            os.chdir(change_dir)

            # Start the aider session
            process = subprocess.Popen(["aider"], stdin=slave_fd, stdout=slave_fd, stderr=slave_fd, preexec_fn=os.setsid)

            # Set the terminal to raw mode
            tty.setraw(sys.stdin.fileno())

            # Write the initial text to the master file descriptor
            if aider_context:
                os.write(master_fd, aider_context.encode())
                os.write(master_fd, b"\n")  # Add a newline to "send" the command
                time.sleep(0.5)  # Add a small delay to allow processing

            # Main loop to handle I/O
            while process.poll() is None:
                import select as os_select

                r, w, e = os_select.select([sys.stdin, master_fd], [], [], 0.1)
                if sys.stdin in r:
                    data = os.read(sys.stdin.fileno(), 1024)
                    os.write(master_fd, data)
                if master_fd in r:
                    data = os.read(master_fd, 1024)
                    if data:
                        os.write(sys.stdout.fileno(), data)
                    else:
                        break

            return_code = process.wait()

            if return_code == 0:
                return f"Aider session completed for location: {abs_file_location}"
            else:
                return f"Aider session exited with return code: {return_code}"
        finally:
            # Restore the original terminal settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)
    except Exception as error:
        return f"Failed to start aider session: {str(error)}"


GOAL_COMMANDS: Set[Callable] = {
    create_goal,
    rename_goal,
    print_goal,
    add_goal_to_current_context,
    drop_goal_from_current_context_only,
    add_goal_status_update,
    mark_goal_completed,
    delete_goal_permamently,
}

MEMORY_COMMANDS = {
    print_memory,
    create_memory,
}


ASSISTANT_VISIBLE_COMMANDS = (
    {
        contemplate,
        start_aider_session,
        get_user_full_name,
        set_user_full_name,
        get_user_preferred_name,
        set_user_preferred_name,
        start_aider_session,
    }
    | GOAL_COMMANDS
    | MEMORY_COMMANDS
)

USER_ONLY_COMMANDS = {
    reset_system_context,
    print_context_messages,
    print_system_instruction,
    refresh_system_instructions,
    print_available_commands,
}


SYSTEM_COMMANDS = ASSISTANT_VISIBLE_COMMANDS | USER_ONLY_COMMANDS | MEMORY_COMMANDS | GOAL_COMMANDS
