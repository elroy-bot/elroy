import asyncio
import html
import logging
import traceback
from datetime import datetime, timedelta
from functools import partial
from operator import add
from typing import AsyncIterator, Iterator, Optional

from colorama import init
from pytz import UTC
from sqlmodel import select
from toolz import pipe

from ..cli.ui import print_memory_panel
from ..config.constants import EXIT, SYSTEM, USER, RecoverableToolError
from ..config.ctx import ElroyContext
from ..db.db_models import Message
from ..io.base import StdIO
from ..io.cli import CliIO
from ..llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from ..messenger import invoke_slash_command, process_message
from ..repository.context_messages.data_models import ContextMessage
from ..repository.context_messages.operations import (
    get_refreshed_system_message,
    refresh_context_if_needed,
    replace_context_messages,
)
from ..repository.context_messages.queries import get_context_messages
from ..repository.context_messages.transform import (
    get_time_since_most_recent_user_message,
)
from ..repository.context_messages.validations import validate
from ..repository.goals.operations import create_onboarding_goal
from ..repository.goals.queries import get_active_goals
from ..repository.memories.queries import get_active_memories
from ..repository.user.operations import set_user_preferred_name
from ..repository.user.queries import (
    get_assistant_name,
    get_user_preferred_name,
    is_user_exists,
)
from ..utils.utils import datetime_to_string, run_in_background_thread


def handle_message_interactive(ctx: ElroyContext, io: CliIO, tool: Optional[str]):
    message = asyncio.run(io.prompt_user("Enter your message"))
    io.print_stream(process_message(USER, ctx, message, tool))


def handle_message_stdio(ctx: ElroyContext, io: StdIO, message: str, tool: Optional[str]):
    if not is_user_exists(ctx.db.session, ctx.user_token):
        asyncio.run(onboard_non_interactive(ctx))
    io.print_stream(process_message(USER, ctx, message, tool))


def get_user_logged_in_message(ctx: ElroyContext) -> str:
    preferred_name = get_user_preferred_name(ctx)

    if preferred_name == "Unknown":
        preferred_name = "User (preferred name unknown)"

    local_tz = datetime.now().astimezone().tzinfo

    # Get start of today in local timezone
    today_start = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

    # Convert to UTC for database comparison
    today_start_utc = today_start.astimezone(UTC)

    earliest_today_msg = ctx.db.exec(
        select(Message)
        .where(Message.user_id == ctx.user_id)
        .where(Message.role == USER)
        .where(Message.created_at >= today_start_utc)
        .order_by(Message.created_at)  # type: ignore
        .limit(1)
    ).first()

    if earliest_today_msg:
        # Convert UTC time to local timezone for display
        local_time = earliest_today_msg.created_at.replace(tzinfo=UTC).astimezone(local_tz)
        today_summary = f"I first started chatting with {preferred_name} today at {local_time.strftime('%I:%M %p')}."
    else:
        today_summary = f"I haven't chatted with {preferred_name} yet today. I should offer a brief greeting."

    return f"{preferred_name} has logged in. The current time is {datetime_to_string(datetime.now().astimezone())}. {today_summary}"


async def handle_chat(ctx: ElroyContext):
    init(autoreset=True)
    io = ctx.io
    assert isinstance(io, CliIO)

    io.print_title_ruler(get_assistant_name(ctx))
    context_messages = validate(ctx, get_context_messages(ctx))

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
    print_memory_panel(ctx)

    while True:
        io.update_completer(
            get_active_goals(ctx),
            get_active_memories(ctx),
            get_context_messages(ctx),
        )

        user_input = await io.prompt_user()
        if user_input.lower().startswith(f"/{EXIT}") or user_input == EXIT:
            break
        elif user_input:
            await process_and_deliver_msg(USER, ctx, user_input)

        io.rule()
        print_memory_panel(ctx)
        run_in_background_thread(refresh_context_if_needed, ctx)


async def process_and_deliver_msg(role: str, ctx: ElroyContext, user_input: str):
    if user_input.startswith("/") and role == USER:
        try:
            result = await invoke_slash_command(ctx, user_input)
            if isinstance(result, (Iterator, AsyncIterator)):
                ctx.io.print_stream(result)
            else:
                ctx.io.info(result)
        except RecoverableToolError as e:
            ctx.io.info(str(e))
        except Exception as e:
            pipe(
                traceback.format_exception(type(e), e, e.__traceback__),
                "".join,
                html.escape,
                lambda x: x.replace("\n", "<br/>"),
                partial(add, "Error invoking system command: "),
                ctx.io.info,
            )
    else:
        ctx.io.print_stream(process_message(role, ctx, user_input))


async def onboard_interactive(ctx: ElroyContext):
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


async def onboard_non_interactive(ctx: ElroyContext) -> None:
    replace_context_messages(ctx, [get_refreshed_system_message(ctx, [])])
