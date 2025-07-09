import re
import traceback
from bdb import BdbQuit
from datetime import timedelta
from functools import partial
from itertools import tee
from multiprocessing import get_logger
from operator import add
from typing import AsyncIterator, Iterator, Optional

from colorama import init
from pytz import UTC
from sqlmodel import select
from toolz import pipe

from ..cli.ui import print_memory_panel, print_model_selection, print_title_ruler
from ..core.async_tasks import schedule_task
from ..core.constants import EXIT, SYSTEM, USER
from ..core.ctx import ElroyContext
from ..core.tracing import tracer
from ..db.db_models import Message
from ..io.base import ElroyIO
from ..io.cli import CliIO
from ..llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from ..llm.stream_parser import collect
from ..messenger.messenger import process_message
from ..messenger.slash_commands import invoke_slash_command
from ..repository.context_messages.data_models import ContextMessage
from ..repository.context_messages.operations import (
    eject_irrelevant_memories,
    get_refreshed_system_message,
    refresh_context_if_needed,
    replace_context_messages,
)
from ..repository.context_messages.queries import get_context_messages
from ..repository.context_messages.transforms import (
    get_time_since_most_recent_user_message,
)
from ..repository.context_messages.validations import Validator
from ..repository.goals.operations import create_onboarding_goal
from ..repository.goals.queries import get_active_goals
from ..repository.memories.queries import get_active_memories
from ..repository.user.queries import (
    do_get_user_preferred_name,
    get_assistant_name,
    is_user_exists,
)
from ..repository.user.tools import set_user_preferred_name
from ..utils.clock import local_now, local_tz, today_start_local
from ..utils.utils import datetime_to_string

logger = get_logger()


def handle_message_stdio(
    ctx: ElroyContext,
    io: ElroyIO,
    message: str,
    force_tool: Optional[str],
):
    if not is_user_exists(ctx.db.session, ctx.user_token):
        onboard_non_interactive(ctx)
    io.print_stream(
        process_message(
            role=USER,
            ctx=ctx,
            msg=message,
            force_tool=force_tool,
        )
    )


def get_user_logged_in_message(ctx: ElroyContext) -> str:
    preferred_name = do_get_user_preferred_name(ctx.db.session, ctx.user_id)

    if preferred_name == "Unknown":
        preferred_name = "User (preferred name unknown)"

    today_start = today_start_local()

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
        local_time = earliest_today_msg.created_at.replace(tzinfo=UTC).astimezone(local_tz())
        today_summary = f"I first started chatting with {preferred_name} today at {local_time.strftime('%I:%M %p')}."
    else:
        today_summary = f"I haven't chatted with {preferred_name} yet today. I should offer a brief greeting (less than 50 words)."

    return f"{preferred_name} has logged in. The current time is {datetime_to_string(local_now())}. {today_summary}"


def handle_chat(io: CliIO, enable_greeting: bool, ctx: ElroyContext):
    init(autoreset=True)

    print_title_ruler(io, get_assistant_name(ctx))

    context_messages = Validator(ctx, get_context_messages(ctx)).validated_msgs()

    if not enable_greeting:
        logger.info("assistant greeting disabled")
    elif (get_time_since_most_recent_user_message(context_messages) or timedelta()) < ctx.min_convo_age_for_greeting:
        logger.info(f"User has interacted within {ctx.min_convo_age_for_greeting}, skipping greeting.")
    else:
        print_model_selection(io, ctx)
        do_get_user_preferred_name(ctx.db.session, ctx.user_id)
        process_and_deliver_msg(
            io,
            SYSTEM,
            ctx,
            get_user_logged_in_message(ctx),
            False,
        )
    if io.show_memory_panel:
        print_memory_panel(io, ctx)

    while True:
        io.update_completer(
            get_active_goals(ctx),
            get_active_memories(ctx),
            list(get_context_messages(ctx)),
        )

        user_input = io.prompt_user(ctx.thread_pool, 3)
        if user_input.lower().startswith(f"/{EXIT}") or user_input == EXIT:
            break
        elif user_input:
            process_and_deliver_msg(
                io,
                USER,
                ctx,
                user_input,
            )

            if io.show_memory_panel:
                io.rule()
                print_memory_panel(io, ctx)
            schedule_task(refresh_context_if_needed, ctx, replace=True, delay_seconds=5)
            schedule_task(eject_irrelevant_memories, ctx, replace=True, delay_seconds=30)


@tracer.agent
def process_and_deliver_msg(io: CliIO, role: str, ctx: ElroyContext, user_input: str, enable_tools: bool = True):
    if user_input.startswith("/ask"):
        user_input = re.sub("^/ask", "", user_input)

    if user_input.startswith("/") and role == USER:
        try:
            result = invoke_slash_command(io, ctx, user_input)
            if isinstance(result, (Iterator, AsyncIterator)):
                io.print_stream(result)
            else:
                io.info(result)
        except BdbQuit:
            ctx.db.rollback()
            io.print("Cancelled")
        except KeyboardInterrupt:
            ctx.db.rollback()
            io.print("Cancelled")
        except Exception as e:
            pipe(
                traceback.format_exception(type(e), e, e.__traceback__),
                "".join,
                partial(add, "Error invoking system command: "),
                io.info,
            )
            ctx.db.rollback()
    else:
        try:
            stream_to_print, stream_to_collect = tee(
                process_message(
                    role=role,
                    ctx=ctx,
                    msg=user_input,
                    enable_tools=enable_tools,
                )
            )

            io.print_stream(stream_to_print)
            return collect(stream_to_collect)
        except KeyboardInterrupt:
            ctx.db.rollback()


def onboard_interactive(io: CliIO, ctx: ElroyContext):
    from .chat import process_and_deliver_msg

    preferred_name = io.prompt_user(
        ctx.thread_pool,
        3,
        f"Welcome! I'm assistant named {get_assistant_name(ctx)}. What should I call you?",
    )

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

    process_and_deliver_msg(
        io,
        SYSTEM,
        ctx,
        f"User {preferred_name} has been onboarded. Say hello and introduce yourself.",
        False,
    )


def onboard_non_interactive(ctx: ElroyContext) -> None:
    replace_context_messages(ctx, [get_refreshed_system_message(ctx, [])])
