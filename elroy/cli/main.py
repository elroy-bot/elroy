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

from ..cli.updater import check_updates, ensure_current_db_migration, version_callback
from ..config.config import ROOT_DIR, ElroyContext, get_config, session_manager
from ..config.constants import (
    CLI_USER_ID,
    DEFAULT_ASSISTANT_COLOR,
    DEFAULT_INPUT_COLOR,
    DEFAULT_INTERNAL_THOUGHT_COLOR,
    DEFAULT_SYSTEM_MESSAGE_COLOR,
    DEFAULT_WARNING_COLOR,
    INITIAL_REFRESH_WAIT_SECONDS,
    MIN_CONVO_AGE_FOR_GREETING,
)
from ..docker_postgres import is_docker_running, start_db, stop_db
from ..io.base import StdIO
from ..io.cli import CliIO
from ..logging_config import setup_logging
from ..messaging.context import context_refresh
from ..messaging.messenger import process_message
from ..onboard_user import onboard_user
from ..repository.data_models import SYSTEM, USER
from ..repository.goals.queries import get_goal_names
from ..repository.memory import (
    get_memory_names,
    get_relevant_memories,
    manually_record_user_memory,
)
from ..repository.message import get_time_since_most_recent_user_message
from ..repository.user import is_user_exists
from ..system_commands import SYSTEM_COMMANDS, contemplate, invoke_system_command
from ..tools.user_preferences import get_user_preferred_name, set_user_preferred_name
from ..utils.utils import datetime_to_string

app = typer.Typer(help="Elroy CLI", context_settings={"obj": {}})


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
    show_internal_thought_monologue: bool = typer.Option(
        False, help="Show the assistant's internal thought monologue like memory consolidation and internal reflection."
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
    internal_thought_color: str = typer.Option(DEFAULT_INTERNAL_THOUGHT_COLOR, help="Color for internal thought messages."),
):
    """Common parameters."""
    ctx.obj = {
        "postgres_url": postgres_url,
        "show_internal_thought_monologue": show_internal_thought_monologue,
        "openai_api_key": openai_api_key,
        "context_window_token_limit": context_window_token_limit,
        "log_file_path": log_file_path,
        "use_docker_postgres": use_docker_postgres,
        "stop_docker_postgres_on_exit": stop_docker_postgres_on_exit,
        "system_message_color": system_message_color,
        "user_input_color": user_input_color,
        "assistant_color": assistant_color,
        "warning_color": warning_color,
        "internal_thought_color": internal_thought_color,
        "is_tty": sys.stdin.isatty(),
    }


@app.command()
def remember(
    ctx: typer.Context,
    file: Optional[str] = typer.Option(None, "--file", "-f", help="File to read memory text from"),
):
    """Create a new memory from stdin or interactively"""

    with init_elroy_context(ctx) as context:
        memory_name = None
        if not sys.stdin.isatty():
            memory_text = sys.stdin.read()
            metadata = "Memory ingested from stdin\n" f"Ingested at: {datetime_to_string(datetime.now())}\n"
            memory_text = f"{metadata}\n{memory_text}"
            memory_name = f"Memory from stdin, ingested {datetime_to_string(datetime.now())}"
        elif file:
            try:
                with open(file, "r") as f:
                    memory_text = f.read()
                # Add file metadata
                file_stat = os.stat(file)
                metadata = "Memory ingested from file"
                "File: {file}"
                f"Last modified: {datetime_to_string(datetime.fromtimestamp(file_stat.st_mtime))}\n"
                f"Created at: {datetime_to_string(datetime.fromtimestamp(file_stat.st_ctime))}"
                f"Size: {file_stat.st_size} bytes\n"
                f"Ingested at: {datetime_to_string(datetime.now())}\n"
                memory_text = f"{memory_text}\n{metadata}"
                memory_name = f"Memory from file: {file}, ingested {datetime_to_string(datetime.now())}"
            except Exception as e:
                context.io.sys_message(f"Error reading file: {e}")
                exit(1)
        else:
            # Get the memory text from user
            memory_text = asyncio.run(context.io.prompt_user("Enter the memory text:"))
            memory_text += f"\nManually entered memory, at: {datetime_to_string(datetime.now())}"
            # Optionally get memory name
            memory_name = asyncio.run(context.io.prompt_user("Enter memory name (optional, press enter to skip):"))
        try:
            manually_record_user_memory(context, memory_text, memory_name)
            context.io.sys_message(f"Memory created: {memory_name}")
            exit(0)
        except ValueError as e:
            context.io.assistant_msg(f"Error creating memory: {e}")
            exit(1)


@app.command()
def chat(ctx: typer.Context):
    """Start the Elroy chat interface"""

    if not sys.stdin.isatty():
        with init_elroy_context(ctx) as context:
            for line in sys.stdin:
                process_and_deliver_msg(context, line)
        return

    with init_elroy_context(ctx) as context:
        check_updates(context)
        asyncio.run(main_chat(context))
        context.io.sys_message(f"Exiting...")


def process_and_deliver_msg(context: ElroyContext, user_input: str, role=USER):
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


def run_in_background_thread(fn, context, *args):
    # hack to get a new session for the thread
    with session_manager(context.config.postgres_url) as session:
        thread = threading.Thread(
            target=fn,
            args=(ElroyContext(user_id=CLI_USER_ID, session=session, config=context.config, io=context.io), *args),
            daemon=True,
        )
        thread.start()


async def main_chat(context: ElroyContext[CliIO]):
    init(autoreset=True)

    run_in_background_thread(
        periodic_context_refresh,
        context,
        context.config.context_refresh_interval_seconds,
    )

    context.io.print_title_ruler()

    if not is_user_exists(context):
        context.io.notify_warning("Elroy is in alpha release")
        name = await context.io.prompt_user("Welcome to Elroy! What should I call you?")
        user_id = onboard_user(context.session, context.io, context.config, name)
        assert isinstance(user_id, int)

        set_user_preferred_name(context, name)
        pipe(context, get_relevant_memories, context.io.print_memory_panel)
        process_and_deliver_msg(context, "Elroy user {name} has been onboarded. Say hello and introduce yourself.", role=SYSTEM)

    elif (get_time_since_most_recent_user_message(context) or timedelta()) < MIN_CONVO_AGE_FOR_GREETING:
        logging.info("User has interacted recently, skipping greeting.")
        pipe(context, get_relevant_memories, context.io.print_memory_panel)
    else:
        preferred_name = get_user_preferred_name(context)
        pipe(context, get_relevant_memories, context.io.print_memory_panel)

        process_and_deliver_msg(
            context,
            f"{preferred_name} has logged in. The current time is {datetime_to_string(datetime.now())}. I should offer a brief greeting.",
            SYSTEM,
        )

    while True:
        try:

            context.io.update_completer(get_goal_names(context), get_memory_names(context))

            user_input = await context.io.prompt_user()
            if user_input.lower().startswith("/exit") or user_input == "exit":
                break
            elif user_input:
                process_and_deliver_msg(context, user_input)
                run_in_background_thread(contemplate, context)
        except EOFError:
            break

        context.io.rule()
        pipe(context, get_relevant_memories, context.io.print_memory_panel)


def main():
    if len(sys.argv) == 1:
        sys.argv.append("chat")
    app()


if __name__ == "__main__":
    main()
