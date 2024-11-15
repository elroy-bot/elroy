import asyncio
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Generator

import typer
from pytz import UTC
from sqlmodel import select

from ..config.config import ElroyContext, session_manager
from ..config.constants import CLI_USER_ID, INITIAL_REFRESH_WAIT_SECONDS
from ..docker_postgres import is_docker_running, start_db, stop_db
from ..io.base import StdIO
from ..io.cli import CliIO
from ..logging_config import setup_logging
from ..messaging.context import context_refresh
from ..repository.data_models import USER, Message
from ..tools.user_preferences import get_user_preferred_name
from ..utils.utils import datetime_to_string
from .updater import ensure_current_db_migration


def periodic_context_refresh(context: ElroyContext, interval_seconds: float):
    """Run context refresh in a background thread"""
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def refresh_loop(context: ElroyContext):
        await asyncio.sleep(INITIAL_REFRESH_WAIT_SECONDS)
        while True:
            try:
                logging.info("Refreshing context")
                await context_refresh(context)  # Keep this async
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logging.error(f"Error in periodic context refresh: {e}")
                context.session.rollback()

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
        setup_logging(ctx.obj["log_file_path"])

        if ctx.obj["use_docker_postgres"]:
            if is_docker_running():
                start_db()
            else:
                raise typer.BadParameter(
                    "Elroy was started with use_docker_postgres set to True, but no Docker container is running. Please either start a Docker container, provide a postgres_url parameter, or set the ELROY_POSTGRES_URL environment variable."
                )

        # Check if migrations need to be run
        config = ctx.obj["elroy_config"]
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
