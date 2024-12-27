import asyncio
import html
import logging
import traceback
from datetime import timedelta
from functools import partial
from operator import add
from typing import Iterable, Optional

from colorama import init
from toolz import concat, pipe, unique
from toolz.curried import filter, map

from ..config.constants import SYSTEM, USER
from ..config.ctx import ElroyContext
from ..io.base import StdIO
from ..io.cli import CliIO
from ..llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from ..messaging.context import get_refreshed_system_message
from ..messaging.messenger import process_message, validate
from ..repository.data_models import ContextMessage
from ..repository.goals.operations import create_onboarding_goal
from ..repository.goals.queries import get_active_goals
from ..repository.memory import get_active_memories
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
from .context import get_user_logged_in_message, periodic_context_refresh


def handle_message_interactive(ctx: ElroyContext, io: CliIO, tool: Optional[str]):
    pipe(
        io.prompt_user("Enter your message"),
        asyncio.run,
        lambda input: process_message(USER, ctx, input, tool),
        io.assistant_msg,
    )


def handle_message_stdio(ctx: ElroyContext, io: StdIO, message: str, tool: Optional[str]):
    pipe(
        process_message(USER, ctx, message, tool),
        ctx.io.assistant_msg,
    )


async def run_chat(ctx: ElroyContext):
    init(autoreset=True)
    io = ctx.io
    assert isinstance(io, CliIO)
    run_in_background_thread(periodic_context_refresh, ctx)

    io.print_title_ruler()
    context_messages = get_context_messages(ctx)

    validated_messages = validate(
        ctx,
        context_messages,
    )

    if context_messages != validated_messages:
        replace_context_messages(ctx, validated_messages)
        logging.warning("Context messages were repaired")
        context_messages = get_context_messages(ctx)

    print_memory_panel(ctx, context_messages)

    if not (ctx.enable_assistant_greeting):
        logging.info("enable_assistant_greeting param disabled, skipping greeting")
    elif (get_time_since_most_recent_user_message(context_messages) or timedelta()) < ctx.min_convo_age_for_greeting:
        logging.info("User has interacted recently, skipping greeting.")
    else:
        get_user_preferred_name(ctx)

        await process_and_deliver_msg(
            SYSTEM,
            ctx,
            get_user_logged_in_message(ctx),
        )

    while True:
        try:
            io.update_completer(get_active_goals(ctx), get_active_memories(ctx), context_messages)

            user_input = await io.prompt_user()
            if user_input.lower().startswith("/exit") or user_input == "exit":
                break
            elif user_input:
                await process_and_deliver_msg(USER, ctx, user_input)
                run_in_background_thread(contemplate, ctx)
        except EOFError:
            break

        io.rule()
        context_messages = get_context_messages(ctx)
        print_memory_panel(ctx, context_messages)


async def process_and_deliver_msg(role: str, ctx: ElroyContext, user_input: str):
    if user_input.startswith("/") and role == USER:
        cmd = user_input[1:].split()[0]

        if cmd.lower() not in {f.__name__ for f in SYSTEM_COMMANDS}:
            ctx.io.sys_message(f"Unknown command: {cmd}")
        else:
            try:
                result = await invoke_system_command(ctx, user_input)
                if result:
                    ctx.io.sys_message(str(result))
            except Exception as e:
                pipe(
                    traceback.format_exception(type(e), e, e.__traceback__),
                    "".join,
                    html.escape,
                    lambda x: x.replace("\n", "<br/>"),
                    partial(add, "Error invoking system command: "),
                    ctx.io.sys_message,
                )
    else:
        ctx.io.assistant_msg(process_message(role, ctx, user_input))


def print_memory_panel(ctx: ElroyContext, context_messages: Iterable[ContextMessage]) -> None:
    io = ctx.io
    assert isinstance(io, CliIO)
    pipe(
        context_messages,
        filter(lambda m: not m.created_at or m.created_at > get_utc_now() - ctx.max_in_context_message_age),
        map(lambda m: m.memory_metadata),
        filter(lambda m: m is not None),
        concat,
        map(lambda m: f"{m.memory_type}: {m.name}"),
        unique,
        list,
        sorted,
        io.print_memory_panel,
    )


async def onboard_interactive(ctx: ElroyContext):
    from ..llm.persona import get_assistant_name
    from .chat import process_and_deliver_msg

    io = ctx.io
    assert isinstance(io, CliIO)

    preferred_name = await io.prompt_user(f"Welcome! I'm assistant named {get_assistant_name(ctx)}. What should I call you?")

    set_user_preferred_name(ctx, preferred_name)

    create_onboarding_goal(ctx, preferred_name)

    replace_context_messages(
        ctx,
        [
            get_refreshed_system_message(ctx, []),
            ContextMessage(
                role=SYSTEM,
                content=ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT(preferred_name),
                chat_model=None,
            ),
        ],
    )

    await process_and_deliver_msg(
        SYSTEM,
        ctx,
        f"User {preferred_name} has been onboarded. Say hello and introduce yourself.",
    )
