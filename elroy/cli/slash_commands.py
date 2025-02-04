import inspect
import json
import logging
from inspect import Parameter
from typing import Any, Optional, Union, get_args, get_origin

from rich.console import Group
from rich.pretty import Pretty
from rich.table import Table
from toolz import pipe
from toolz.curried import map

from ..config.constants import ASSISTANT, SYSTEM, TOOL, USER, tool
from ..config.ctx import ElroyContext
from ..llm.client import query_llm
from ..llm.prompts import contemplate_prompt
from ..repository.context_messages.data_models import ContextMessage
from ..repository.context_messages.operations import add_context_messages
from ..repository.context_messages.queries import (
    get_context_messages,
    get_current_system_message,
)
from ..repository.context_messages.transform import format_context_messages
from ..repository.user.queries import get_user_preferred_name


def print_context_messages(ctx: ElroyContext) -> Table:
    """Logs all of the current context messages to stdout

    Args:
        session (Session): _description_
        user_id (int): _description_
    """
    messages = get_context_messages(ctx)

    table = Table(show_header=True, padding=(0, 2), show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Message Details")

    for idx, message in enumerate(messages, 1):
        # Determine style based on role

        # Create message details
        details = [
            f"[bold]ID[/]: {message.id}",
            f"[bold]Role[/]: {message.role}",
            f"[bold]Model[/]: {message.chat_model or ''}",
        ]

        if message.created_at:
            details.append(f"[bold]Created[/]: {message.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        if message.content:
            details.append(f"\n[bold]Content[/]:\n{message.content}")

        if message.tool_calls:
            details.append("[bold]Tool Calls:[/]")
            for tc in message.tool_calls:
                try:
                    tc.function["arguments"] = json.loads(tc.function["arguments"])
                except json.JSONDecodeError:
                    logging.info("Couldn't decode arguments for tool call")
                details.append(Pretty(tc, expand_all=True))  # type: ignore

        table.add_row(
            str(idx),
            Group(*details),
            style={
                ASSISTANT: ctx.params.assistant_color,
                USER: ctx.params.user_input_color,
                SYSTEM: ctx.params.system_message_color,
                TOOL: ctx.params.system_message_color,
            }.get(message.role, "white"),
        )

    return table


def add_internal_thought(ctx: ElroyContext, thought: str) -> str:
    """Inserts internal thought for the assistant. Useful for guiding the assistant's thoughts in a specific direction.

    Args:
        context (ElroyContext): context obj
        thought (str): The thought to add

    Returns:
        str: The result of the internal thought addition
    """

    add_context_messages(
        ctx,
        [
            ContextMessage(
                role=SYSTEM,
                content=thought,
                chat_model=ctx.chat_model.name,
            )
        ],
    )

    return f"Internal thought added: {thought}"


@tool
def contemplate(ctx: ElroyContext, contemplation_prompt: Optional[str] = None) -> str:
    """Contemplate the current context and return a response.

    Args:
        contemplation_prompt (Optional[str]): Custom prompt to guide the contemplation.
            If not provided, will contemplate the current conversation context.

    Returns:
        str: A thoughtful response analyzing the current context and any provided prompt.
    """

    logging.info("Contemplating...")

    user_preferred_name = get_user_preferred_name(ctx)
    context_messages = get_context_messages(ctx)

    msgs_input = format_context_messages(context_messages, user_preferred_name)

    response = query_llm(
        model=ctx.chat_model,
        prompt=msgs_input,
        system=contemplate_prompt(user_preferred_name, contemplation_prompt),
    )

    add_context_messages(
        ctx,
        [
            ContextMessage(
                role=SYSTEM,
                content=response,
                chat_model=ctx.chat_model.name,
            )
        ],
    )

    return response


def help(ctx: ElroyContext) -> Table:
    """Prints the available system commands

    Returns:
        str: The available system commands
    """
    from ..tools.tools_and_commands import SYSTEM_COMMANDS

    commands = pipe(
        SYSTEM_COMMANDS,
        map(
            lambda f: (
                f.__name__,
                inspect.getdoc(f).split("\n")[0],  # type: ignore
            )
        ),
        list,
        sorted,
    )

    table = Table(title="Available Slash Commands")
    table.add_column("Command", justify="left", style="cyan", no_wrap=True)
    table.add_column("Description", justify="left", style="green")

    for command, description in commands:  # type: ignore
        table.add_row(command, description)
    return table


def print_system_instruction(ctx: ElroyContext) -> Optional[str]:
    """Prints the current system instruction for the assistant

    Args:
        user_id (int): user id

    Returns:
        str: The current system instruction
    """

    return pipe(
        get_current_system_message(ctx),
        lambda _: _.content if _ else None,
    )  # type: ignore


def _is_optional(param: Parameter) -> bool:
    return get_origin(param.annotation) is Union and type(None) in get_args(param.annotation)


def _get_casted_value(parameter: Parameter, str_value: str) -> Optional[Any]:
    if not str_value:
        return None
    # detect if it is union
    if _is_optional(parameter):
        arg_type = get_args(parameter.annotation)[0]
    else:
        arg_type = parameter.annotation
    return arg_type(str_value)


def _get_prompt_for_param(param: Parameter) -> str:
    prompt_title = pipe(
        param.name,
        lambda x: x.split("_"),
        map(str.capitalize),
        " ".join,
    )

    if _is_optional(param):
        prompt_title += " (optional)"

    return prompt_title + ">"
