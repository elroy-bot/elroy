import logging
import os
import platform
import pty
import subprocess
import sys
import termios
import time
import tty
import urllib
import urllib.parse
import webbrowser
from dataclasses import asdict
from datetime import datetime
from inspect import signature
from pprint import pformat
from typing import Callable, List, Optional, Set

import scrubadub
from rich.pretty import Pretty
from sqlmodel import select
from toolz import pipe
from toolz.curried import filter

from . import __version__
from .cli.bug_report import create_bug_report
from .config.config import ElroyContext
from .config.constants import BUG_REPORT_LOG_LINES, REPO_ISSUES_URL
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
from .tools.user_preferences import (
    get_user_full_name,
    get_user_preferred_name,
    set_user_full_name,
    set_user_preferred_name,
)
from .utils.ops import experimental
from .utils.utils import obscure_sensitive_info


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
        num_required_non_context_args = len([p for p in params if p.default is p.empty and p.annotation != ElroyContext])

        arg_index = 0
        for param in params:
            if param.annotation == ElroyContext:
                func_args.append(context)
                continue

            if arg_index < len(args) and args[arg_index] not in [None, ""]:  # We have an argument provided
                if param.annotation == str and arg_index == num_required_non_context_args - 1:
                    # Last *required* string param gets remaining args
                    func_args.append(" ".join(args[arg_index:]))
                    break
                else:
                    func_args.append(args[arg_index])
                    arg_index += 1
            elif param.default is not param.empty:
                # Use default value for optional parameter
                continue
            else:
                # Missing required argument
                return f"Error: Missing required argument '{param.name}' for command {command}."

        return func(*func_args)
    except Exception as e:
        return f"Error invoking system command: {e}"


@experimental
def tail_elroy_logs(context: ElroyContext, lines: int = 10) -> str:
    """
    Returns the last `lines` of the Elroy logs.
    Useful for troubleshooting in cases where errors occur (especially with tool calling).

    Args:
        context (ElroyContext): context obj
        lines (int, optional): Number of lines to return. Defaults to 10.

    Returns:
        str: The last `lines` of the Elroy logs
    """
    with open(context.config.log_file_path, "r") as f:
        return "".join(f.readlines()[-lines:])


def print_elroy_config(context: ElroyContext) -> str:
    """
    Prints the current Elroy configuration.
    Useful for troubleshooting and verifying the current configuration.

    Args:
        context (ElroyContext): context obj

    Returns:
        str: The current Elroy configuration
    """
    return str(context.config)


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


def create_bug_report(
    context: ElroyContext,
    title: str,
    description: str,
) -> None:
    """
    Generate a bug report and open it as a GitHub issue.

    Args:
        context: The Elroy context
        title: The title for the bug report
        description: Detailed description of the issue
    """
    # Start building the report
    report = [
        f"# Bug Report: {title}",
        f"\nCreated: {datetime.now().isoformat()}",
        "\n## Description",
        description,
    ]

    # Add system information
    report.extend(
        [
            "\n## System Information",
            f"OS: {platform.system()} {platform.release()}",
            f"Python: {sys.version}",
            f"Elroy Version: {__version__}",
        ]
    )

    # Add configuration if requested
    report.append("\n## Elroy Configuration")
    try:
        report.append("```")
        # Convert to dict and recursively obscure sensitive info
        config_dict = obscure_sensitive_info(asdict(context.config))
        report.append(pformat(config_dict, indent=2, width=80))
        report.append("```")
    except Exception as e:
        report.append(f"Error fetching config: {str(e)}")

    # Add logs if requested
    report.append(f"\n## Recent Logs (last {BUG_REPORT_LOG_LINES} lines)")
    try:
        logs = tail_elroy_logs(context, BUG_REPORT_LOG_LINES)
        report.append("```")
        report.append(logs)
        report.append("```")
    except Exception as e:
        report.append(f"Error fetching logs: {str(e)}")

    # Combine the report
    full_report = scrubadub.clean("\n".join(report))

    # Handle GitHub issue creation if requested
    github_url = None
    base_url = os.path.join(REPO_ISSUES_URL, "new")
    params = {"title": title, "body": full_report}
    github_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    webbrowser.open(github_url)


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
