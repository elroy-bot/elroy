import asyncio
import logging
from contextlib import contextmanager
from datetime import datetime
from itertools import product
from typing import Generator, List

import typer
from prompt_toolkit.completion import WordCompleter
from pytz import UTC
from sqlmodel import select
from toolz import concatv, pipe
from toolz.curried import map

from ..config.config import ElroyContext, session_manager
from ..config.constants import CLI_USER_ID
from ..docker_postgres import is_docker_running, start_db, stop_db
from ..io.base import StdIO
from ..io.cli import CliIO
from ..logging_config import setup_logging
from ..messaging.context import context_refresh, is_memory_in_context
from ..repository.data_models import USER, ContextMessage, Message
from ..repository.goals.queries import get_active_goals
from ..repository.memory import get_active_memories
from ..system_commands import (
    ALL_ACTIVE_GOAL_COMMANDS,
    ALL_ACTIVE_MEMORY_COMMANDS,
    IN_CONTEXT_GOAL_COMMANDS,
    IN_CONTEXT_MEMORY_COMMANDS,
    NON_ARG_PREFILL_COMMANDS,
    NON_CONTEXT_GOAL_COMMANDS,
    NON_CONTEXT_MEMORY_COMMANDS,
    USER_ONLY_COMMANDS,
)
from ..tools.user_preferences import get_user_preferred_name
from ..utils.utils import datetime_to_string
from .updater import ensure_current_db_migration


def periodic_context_refresh(context: ElroyContext):
    """Run context refresh in a background thread"""
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def refresh_loop(context: ElroyContext):
        logging.info(f"Pausing for initial context refresh wait of {context.config.initial_refresh_wait}")
        await asyncio.sleep(context.config.initial_refresh_wait.total_seconds())
        while True:
            try:
                logging.info("Refreshing context")
                await context_refresh(context)  # Keep this async
                logging.info(f"Wait for {context.config.context_refresh_interval} before next context refresh")
                await asyncio.sleep(context.config.context_refresh_interval.total_seconds())
            except Exception as e:
                logging.error(f"Error in periodic context refresh: {e}")
                context.session.rollback()

                if context.config.debug_mode:
                    raise e

    try:
        # hack to get a new session for the thread
        with session_manager(context.config.postgres_url) as session:
            loop.run_until_complete(
                refresh_loop(
                    ElroyContext(
                        user_id=CLI_USER_ID,
                        session=session,
                        config=context.config,
                        io=context.io,
                    )
                )
            )
    finally:
        loop.close()


@contextmanager
def init_elroy_context(ctx: typer.Context) -> Generator[ElroyContext, None, None]:
    """Create an ElroyContext as a context manager"""

    if ctx.obj["is_tty"]:
        io = CliIO(
            ctx.obj["show_internal_thought_monologue"],
            ctx.obj["system_message_color"],
            ctx.obj["assistant_color"],
            ctx.obj["user_input_color"],
            ctx.obj["warning_color"],
            ctx.obj["internal_thought_color"],
        )
    else:
        io = StdIO()

    try:
        config = ctx.obj["elroy_config"]
        setup_logging(config.log_file_path)

        if ctx.obj["use_docker_postgres"]:
            if is_docker_running():
                start_db()
            else:
                raise typer.BadParameter(
                    "Elroy was started with use_docker_postgres set to True, but no Docker container is running. Please either start a Docker container, provide a postgres_url parameter, or set the ELROY_POSTGRES_URL environment variable."
                )

        ensure_current_db_migration(io, config.postgres_url)

        with session_manager(config.postgres_url) as session:
            yield ElroyContext(
                user_id=CLI_USER_ID,
                session=session,
                config=config,
                io=io,
            )

    finally:
        if ctx.obj["use_docker_postgres"] and ctx.obj["stop_docker_postgres_on_exit"]:
            io.sys_message("Stopping Docker Postgres container...")
            stop_db()


def get_user_logged_in_message(context: ElroyContext) -> str:
    preferred_name = get_user_preferred_name(context)

    if preferred_name == "Unknown":
        preferred_name = "User apreferred name unknown)"

    local_tz = datetime.now().astimezone().tzinfo

    # Get start of today in local timezone
    today_start = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

    # Convert to UTC for database comparison
    today_start_utc = today_start.astimezone(UTC)

    earliest_today_msg = context.session.exec(
        select(Message)
        .where(Message.role == USER)
        .where(Message.created_at >= today_start_utc)
        .order_by(Message.created_at)  # type: ignore
        .limit(1)
    ).first()

    if earliest_today_msg:
        today_summary = (
            f"I first started chatting with {preferred_name} today at {earliest_today_msg.created_at.astimezone().strftime('%I:%M %p')}."
        )
    else:
        today_summary = f"I haven't chatted with {preferred_name} yet today. I should offer a brief greeting."

    return f"{preferred_name} has logged in. The current time is {datetime_to_string(datetime.now().astimezone())}. {today_summary}"


def get_completer(context: ElroyContext[CliIO], context_messages: List[ContextMessage]) -> WordCompleter:
    goals = get_active_goals(context)
    in_context_goal_names = sorted([g.get_name() for g in goals if is_memory_in_context(context_messages, g)])
    non_context_goal_names = sorted([g.get_name() for g in goals if g.get_name() not in in_context_goal_names])

    memories = get_active_memories(context)
    in_context_memories = sorted([m.get_name() for m in memories if is_memory_in_context(context_messages, m)])
    non_context_memories = sorted([m.get_name() for m in memories if m.get_name() not in in_context_memories])

    return pipe(
        concatv(
            product(IN_CONTEXT_GOAL_COMMANDS, in_context_goal_names),
            product(NON_CONTEXT_GOAL_COMMANDS, non_context_goal_names),
            product(ALL_ACTIVE_GOAL_COMMANDS, [g.get_name() for g in goals]),
            product(IN_CONTEXT_MEMORY_COMMANDS, in_context_memories),
            product(NON_CONTEXT_MEMORY_COMMANDS, non_context_memories),
            product(ALL_ACTIVE_MEMORY_COMMANDS, [m.get_name() for m in memories]),
        ),
        map(lambda x: f"/{x[0].__name__} {x[1]}"),
        list,
        lambda x: x + [f"/{f.__name__}" for f in NON_ARG_PREFILL_COMMANDS | USER_ONLY_COMMANDS],
        lambda x: WordCompleter(x, sentence=True, pattern=r"^/"),  # type: ignore
    )
