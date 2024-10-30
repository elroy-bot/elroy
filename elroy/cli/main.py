import asyncio
import logging
import os
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Generator, Optional

import typer
from colorama import init
from toolz import pipe

from elroy.cli.updater import (check_updates, ensure_current_db_migration,
                               version_callback)
from elroy.config import ROOT_DIR, ElroyContext, get_config, session_manager
from elroy.docker_postgres import is_docker_running, start_db, stop_db
from elroy.io.base import ElroyIO, StdIO
from elroy.io.cli import CliIO
from elroy.logging_config import setup_logging
from elroy.memory import get_memory_names, get_relevant_memories
from elroy.onboard_user import onboard_user
from elroy.store.data_models import SYSTEM, USER
from elroy.store.goals import get_goal_names
from elroy.store.message import get_time_since_most_recent_user_message
from elroy.store.user import is_user_exists
from elroy.system.parameters import (CLI_USER_ID, DEFAULT_ASSISTANT_COLOR,
                                     DEFAULT_INPUT_COLOR,
                                     DEFAULT_SYSTEM_MESSAGE_COLOR,
                                     DEFAULT_WARNING_COLOR,
                                     MIN_CONVO_AGE_FOR_GREETING)
from elroy.system.utils import datetime_to_string
from elroy.system_context import context_refresh
from elroy.tools.functions.user_preferences import (get_user_preferred_name,
                                                    set_user_preferred_name)
from elroy.tools.messenger import process_message
from elroy.tools.system_commands import SYSTEM_COMMANDS, invoke_system_command

app = typer.Typer(help="Elroy CLI", context_settings={"obj": {}})


@contextmanager
def init_elroy_context(ctx: typer.Context, io: Optional[ElroyIO] = None) -> Generator[ElroyContext, None, None]:
    """Create an ElroyContext as a context manager"""

    if not io:
        io = CliIO(
            ctx.obj["system_message_color"],
            ctx.obj["assistant_color"],
            ctx.obj["user_input_color"],
            ctx.obj["warning_color"],
        )

    try:
        setup_logging(ctx.obj["log_file_path"])

        if ctx.obj["use_docker_postgres"]:
            if ctx.obj["postgres_url"] is not None:
                logging.info("postgres_url is set, ignoring use_docker_postgres set to True")

            else:
                if not is_docker_running():
                    io.sys_message(
                        "Docker is not running, and elroy started with --use_docker_postgres. Please start Docker and try again."
                    )
                    exit(1)
                ctx.obj["postgres_url"] = start_db()

        assert ctx.obj["postgres_url"], "Database URL is required"
        assert ctx.obj["openai_api_key"], "OpenAI API key is required"

        # Check if migrations need to be run
        ensure_current_db_migration(io, ctx.obj["postgres_url"])

        config = get_config(
            postgres_url=ctx.obj["postgres_url"],
            openai_api_key=ctx.obj["openai_api_key"],
            context_window_token_limit=ctx.obj["context_window_token_limit"],
        )

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


@app.callback()
def common(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", callback=version_callback, is_eager=True, help="Show version and exit."),
    postgres_url: Optional[str] = typer.Option(
        None, envvar="ELROY_POSTGRES_URL", help="Postgres URL to use for Elroy. If set, ovverrides use_docker_postgres."
    ),
    openai_api_key: Optional[str] = typer.Option(None, envvar="OPENAI_API_KEY", help="OpenAI API key, required."),
    context_window_token_limit: Optional[int] = typer.Option(
        None, envvar="ELROY_CONTEXT_WINDOW_TOKEN_LIMIT", help="How many tokens to keep in context before compressing."
    ),
    log_file_path: str = typer.Option(
        os.path.join(ROOT_DIR, "logs", "elroy.log"), envvar="ELROY_LOG_FILE_PATH", help="Where to write logs."
    ),
    use_docker_postgres: Optional[bool] = typer.Option(
        True,
        envvar="USE_DOCKER_POSTGRES",
        help="If true and postgres_url is not set, will attempt to start a Docker container for Postgres.",
    ),
    stop_docker_postgres_on_exit: Optional[bool] = typer.Option(
        False, envvar="STOP_DOCKER_POSTGRES_ON_EXIT", help="Whether or not to stop the Postgres container on exit."
    ),
    system_message_color: str = typer.Option(DEFAULT_SYSTEM_MESSAGE_COLOR, help="Color for system messages."),
    user_input_color: str = typer.Option(DEFAULT_INPUT_COLOR, help="Color for user input."),
    assistant_color: str = typer.Option(DEFAULT_ASSISTANT_COLOR, help="Color for assistant output."),
    warning_color: str = typer.Option(DEFAULT_WARNING_COLOR, help="Color for warning messages."),
):
    """Common parameters."""
    ctx.obj = {
        "postgres_url": postgres_url,
        "openai_api_key": openai_api_key,
        "context_window_token_limit": context_window_token_limit,
        "log_file_path": log_file_path,
        "use_docker_postgres": use_docker_postgres,
        "stop_docker_postgres_on_exit": stop_docker_postgres_on_exit,
        "system_message_color": system_message_color,
        "user_input_color": user_input_color,
        "assistant_color": assistant_color,
        "warning_color": warning_color,
    }


@app.command()
def chat(ctx: typer.Context):
    """Start the Elroy chat interface"""

    if not sys.stdin.isatty():
        with init_elroy_context(ctx, StdIO()) as context:
            for line in sys.stdin:
                process_and_deliver_msg(context, line)
        return

    with init_elroy_context(ctx) as context:
        check_updates(context)
        asyncio.run(main_chat(context))
        context.io.sys_message(f"Exiting...")


def process_and_deliver_msg(context: ElroyContext[CliIO], user_input: str, role=USER):
    if user_input.startswith("/") and role == USER:
        cmd = user_input[1:].split()[0]

        if cmd.lower() not in {f.__name__ for f in SYSTEM_COMMANDS}:
            context.io.assistant_msg(f"Unknown command: {cmd}")
        else:
            try:
                context.io.sys_message(invoke_system_command(context, user_input))
            except Exception as e:
                context.io.sys_message(f"Error invoking system command: {e}")
    else:
        context.io.assistant_msg(process_message(context, user_input, role))

    context.io.rule()


def periodic_context_refresh(context: ElroyContext, interval_seconds: float):
    """Run context refresh in a background thread"""
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def refresh_loop(context: ElroyContext):
        while True:
            try:
                logging.info("Refreshing context")
                await context_refresh(context)  # Keep this async
                await asyncio.sleep(interval_seconds)
            except Exception as e:
                logging.error(f"Error in periodic context refresh: {e}")

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


async def main_chat(context: ElroyContext[CliIO]):
    init(autoreset=True)

    # Start background refresh task
    refresh_thread = threading.Thread(
        target=periodic_context_refresh,
        args=(context, context.config.context_refresh_interval_seconds),
        daemon=True,  # Makes thread exit when main program exits
    )
    refresh_thread.start()

    context.io.print_title_ruler()

    if not is_user_exists(context):
        context.io.notify_warning("Elroy is in alpha release")
        name = await context.io.prompt_user("Welcome to Elroy! What should I call you?")
        user_id = onboard_user(context.session, context.io, context.config, name)
        assert isinstance(user_id, int)

        set_user_preferred_name(context, name)
        process_and_deliver_msg(context, "Elroy user {name} has been onboarded. Say hello and introduce yourself.", role=SYSTEM)

    elif (get_time_since_most_recent_user_message(context) or timedelta()) < MIN_CONVO_AGE_FOR_GREETING:
        logging.info("User has interacted recently, skipping greeting.")
    else:
        preferred_name = get_user_preferred_name(context)

        process_and_deliver_msg(
            context,
            f"{preferred_name} has logged in. The current time is {datetime_to_string(datetime.now())}. I should offer a brief greeting.",
            SYSTEM,
        )

    while True:
        try:

            context.io.update_completer(get_goal_names(context), get_memory_names(context))
            pipe(context, get_relevant_memories, context.io.print_memory_panel)

            user_input = await context.io.prompt_user()
            if user_input.lower().startswith("/exit") or user_input == "exit":
                break
            elif user_input:
                process_and_deliver_msg(context, user_input)
        except EOFError:
            break


def main():
    if len(sys.argv) == 1:
        sys.argv.append("chat")
    app()


if __name__ == "__main__":
    main()
