import asyncio
import logging
import sys
from datetime import timedelta
from functools import partial
from typing import Iterable

import typer
from colorama import init
from toolz import concat, pipe, unique
from toolz.curried import filter, map

from ..config.config import ElroyContext
from ..messaging.messenger import process_message, validate
from ..repository.data_models import SYSTEM, USER, ContextMessage
from ..repository.message import (
    get_context_messages,
    get_time_since_most_recent_user_message,
    replace_context_messages,
)
from ..system_commands import SYSTEM_COMMANDS, contemplate
from ..tools.user_preferences import get_user_preferred_name
from ..utils.clock import get_utc_now
from ..utils.utils import run_in_background_thread
from .commands import invoke_system_command
from .config import cli_elroy_context, cli_elroy_context_interactive
from .context import get_completer, get_user_logged_in_message, periodic_context_refresh


def handle_message(ctx: typer.Context):
    if sys.stdin.isatty() and not ctx.params.get("message"):
        with cli_elroy_context_interactive(ctx) as context:
            pipe(
                context.io.prompt_user("Enter your message"),
                asyncio.run,
                lambda input: process_message(USER, context, input, ctx.params.get("tool")),
                partial(process_message, USER, context),
                context.io.assistant_msg,
            )
    else:
        with cli_elroy_context(ctx) as context:
            message = ctx.params.get("message")
            assert message is not None

            if not sys.stdin.isatty():
                message += "\n" + sys.stdin.read()

            assert message is not None
            assert isinstance(message, str)
            pipe(
                process_message(USER, context, message, ctx.params.get("tool")),
                context.io.assistant_msg,
            )


def handle_chat(ctx: typer.Context):
    if sys.stdin.isatty():
        with cli_elroy_context_interactive(ctx) as context:
            asyncio.run(chat(context))
    else:
        ctx.params["message"] = sys.stdin.read()
        handle_message(ctx)


async def chat(context: ElroyContext):
    init(autoreset=True)

    run_in_background_thread(periodic_context_refresh, context)

    context.io.print_title_ruler()
    context_messages = get_context_messages(context)

    validated_messages = validate(context.config, context_messages)

    if context_messages != validated_messages:
        replace_context_messages(context, validated_messages)
        logging.warning("Context messages were repaired")
        context_messages = get_context_messages(context)

    print_memory_panel(context, context_messages)

    if not (context.config.enable_assistant_greeting):
        logging.info("enable_assistant_greeting param disabled, skipping greeting")
    elif (get_time_since_most_recent_user_message(context_messages) or timedelta()) < context.config.min_convo_age_for_greeting:
        logging.info("User has interacted recently, skipping greeting.")
    else:
        get_user_preferred_name(context)

        # TODO: should include some information about how long the user has been talking to Elroy
        await process_and_deliver_msg(
            SYSTEM,
            context,
            get_user_logged_in_message(context),
        )

    while True:
        try:
            context.io.update_completer(get_completer(context, context_messages))

            user_input = await context.io.prompt_user()
            if user_input.lower().startswith("/exit") or user_input == "exit":
                break
            elif user_input:
                await process_and_deliver_msg(USER, context, user_input)
                run_in_background_thread(contemplate, context)
        except EOFError:
            break

        context.io.rule()
        context_messages = get_context_messages(context)
        print_memory_panel(context, context_messages)


async def process_and_deliver_msg(role: str, context: ElroyContext, user_input: str):
    if user_input.startswith("/") and role == USER:
        cmd = user_input[1:].split()[0]

        if cmd.lower() not in {f.__name__ for f in SYSTEM_COMMANDS}:
            context.io.sys_message(f"Unknown command: {cmd}")
        else:
            try:
                result = await invoke_system_command(context, user_input)
                context.io.sys_message(result)
            except Exception as e:
                context.io.sys_message(f"Error invoking system command: {e}")
    else:
        context.io.assistant_msg(process_message(role, context, user_input))


def print_memory_panel(context: ElroyContext, context_messages: Iterable[ContextMessage]) -> None:
    pipe(
        context_messages,
        filter(lambda m: not m.created_at or m.created_at > get_utc_now() - context.config.max_in_context_message_age),
        map(lambda m: m.memory_metadata),
        filter(lambda m: m is not None),
        concat,
        map(lambda m: f"{m.memory_type}: {m.name}"),
        unique,
        list,
        sorted,
        context.io.print_memory_panel,
    )
