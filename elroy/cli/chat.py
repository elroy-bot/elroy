import asyncio
import html
import logging
import sys
import traceback
from datetime import timedelta
from functools import partial
from operator import add
from typing import Iterable

import typer
from colorama import init
from toolz import concat, pipe, unique
from toolz.curried import filter, map

from ..config.config import ElroyContext
from ..config.constants import SYSTEM, USER
from ..io.base import StdIO
from ..io.cli import CliIO
from ..llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from ..messaging.context import get_refreshed_system_message
from ..messaging.messenger import process_message, validate
from ..repository.data_models import ContextMessage
from ..repository.goals.operations import create_onboarding_goal
from ..repository.message import (
    get_context_messages,
    get_time_since_most_recent_user_message,
    replace_context_messages,
)
from ..system_commands import SYSTEM_COMMANDS, contemplate
from ..tools.user_preferences import get_user_preferred_name, set_user_preferred_name
from ..utils.clock import get_utc_now
from ..utils.utils import run_in_background_thread
from .commands import invoke_system_command
from .config import (
    get_user_token,
    init_cli_io,
    init_config,
    init_db,
    init_elroy_context,
)
from .context import get_user_logged_in_message, periodic_context_refresh


def handle_message(ctx: typer.Context):
    config = init_config(ctx)
    user_token = get_user_token(ctx)
    with init_db(ctx) as db:
        if sys.stdin.isatty() and not ctx.params.get("message"):
            context, _new_user_created = init_elroy_context(db, init_cli_io(ctx), config, user_token)
            pipe(
                context.io.prompt_user("Enter your message"),
                asyncio.run,
                lambda input: process_message(USER, context, input, ctx.params.get("tool")),
                partial(process_message, USER, context),
                context.io.assistant_msg,
            )
        else:
            context, _new_user_created = init_elroy_context(db, StdIO(), config, user_token)
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
        with init_db(ctx) as db:
            context, new_user_created = init_elroy_context(db, init_cli_io(ctx), init_config(ctx), get_user_token(ctx))
            if new_user_created:
                asyncio.run(onboard_interactive(context))

            asyncio.run(chat(context))
    else:
        ctx.params["message"] = sys.stdin.read()
        handle_message(ctx)


async def chat(context: ElroyContext[CliIO]):
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

        await process_and_deliver_msg(
            SYSTEM,
            context,
            get_user_logged_in_message(context),
        )

    while True:
        try:
            context.io.update_completer(context, context_messages)

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
                if result:
                    context.io.sys_message(str(result))
            except Exception as e:
                pipe(
                    traceback.format_exception(type(e), e, e.__traceback__),
                    "".join,
                    html.escape,
                    lambda x: x.replace("\n", "<br/>"),
                    partial(add, "Error invoking system command: "),
                    context.io.sys_message,
                )
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


async def onboard_interactive(context: ElroyContext[CliIO]):
    from .chat import process_and_deliver_msg

    assert isinstance(context.io, CliIO)

    preferred_name = await context.io.prompt_user("Welcome to Elroy! What should I call you?")

    set_user_preferred_name(context, preferred_name)

    create_onboarding_goal(context, preferred_name)

    replace_context_messages(
        context,
        [
            get_refreshed_system_message(context, []),
            ContextMessage(
                role=SYSTEM,
                content=ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT(preferred_name),
                chat_model=None,
            ),
        ],
    )

    await process_and_deliver_msg(
        SYSTEM,
        context,
        f"Elroy user {preferred_name} has been onboarded. Say hello and introduce yourself.",
    )
