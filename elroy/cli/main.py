import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Iterable, Optional

import typer
from colorama import init
from litellm import anthropic_models, open_ai_chat_completion_models
from toolz import concat, pipe, unique
from toolz.curried import filter, map

from ..cli.updater import check_updates, version_callback
from ..config.config import ROOT_DIR, ElroyContext, get_config
from ..config.constants import (
    DEFAULT_ASSISTANT_COLOR,
    DEFAULT_CHAT_MODEL_NAME,
    DEFAULT_CONTEXT_WINDOW_LIMIT,
    DEFAULT_EMBEDDING_MODEL_NAME,
    DEFAULT_INPUT_COLOR,
    DEFAULT_INTERNAL_THOUGHT_COLOR,
    DEFAULT_SYSTEM_MESSAGE_COLOR,
    DEFAULT_WARNING_COLOR,
    EMBEDDING_SIZE,
    MIN_CONVO_AGE_FOR_GREETING,
)
from ..docker_postgres import DOCKER_DB_URL
from ..io.cli import CliIO
from ..messaging.messenger import process_message, validate
from ..onboard_user import onboard_user
from ..repository.data_models import SYSTEM, USER, ContextMessage
from ..repository.memory import manually_record_user_memory
from ..repository.message import (
    get_context_messages,
    get_time_since_most_recent_user_message,
    replace_context_messages,
)
from ..repository.user import is_user_exists
from ..system_commands import SYSTEM_COMMANDS, contemplate, invoke_system_command
from ..tools.user_preferences import get_user_preferred_name, set_user_preferred_name
from ..utils.clock import get_utc_now
from ..utils.utils import datetime_to_string, run_in_background_thread
from .context import (
    get_completer,
    get_user_logged_in_message,
    init_elroy_context,
    periodic_context_refresh,
)

app = typer.Typer(help="Elroy CLI", context_settings={"obj": {}})


@app.callback()
def common(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    postgres_url: Optional[str] = typer.Option(
        None,
        envvar="ELROY_POSTGRES_URL",
        help="Postgres URL to use for Elroy. If set, ovverrides use_docker_postgres.",
    ),
    show_internal_thought_monologue: bool = typer.Option(
        False,
        help="Show the assistant's internal thought monologue like memory consolidation and internal reflection.",
    ),
    openai_api_key: Optional[str] = typer.Option(
        None,
        envvar="OPENAI_API_KEY",
        help="OpenAI API key, required for OpenAI (or OpenAI compatible) models.",
    ),
    openai_api_base: Optional[str] = typer.Option(
        None,
        envvar="OPENAI_API_BASE",
        help="OpenAI API (or OpenAI compatible) base URL.",
    ),
    openai_embedding_api_base: Optional[str] = typer.Option(
        None,
        envvar="OPENAI_API_BASE",
        help="OpenAI API (or OpenAI compatible) base URL for embeddings.",
    ),
    openai_organization: Optional[str] = typer.Option(
        None,
        envvar="OPENAI_ORGANIZATION",
        help="OpenAI (or OpenAI compatible) organization ID.",
    ),
    anthropic_api_key: Optional[str] = typer.Option(
        None,
        envvar="ANTHROPIC_API_KEY",
        help="Anthropic API key, required for Anthropic models.",
    ),
    context_window_token_limit: int = typer.Option(
        DEFAULT_CONTEXT_WINDOW_LIMIT,
        envvar="ELROY_CONTEXT_WINDOW_TOKEN_LIMIT",
        help="How many tokens to keep in context before compressing.",
    ),
    log_file_path: str = typer.Option(
        os.path.join(ROOT_DIR, "logs", "elroy.log"),
        envvar="ELROY_LOG_FILE_PATH",
        help="Where to write logs.",
    ),
    use_docker_postgres: Optional[bool] = typer.Option(
        True,
        envvar="USE_DOCKER_POSTGRES",
        help="If true and postgres_url is not set, will attempt to start a Docker container for Postgres.",
    ),
    stop_docker_postgres_on_exit: Optional[bool] = typer.Option(
        False,
        envvar="STOP_DOCKER_POSTGRES_ON_EXIT",
        help="Whether or not to stop the Postgres container on exit.",
    ),
    system_message_color: str = typer.Option(
        DEFAULT_SYSTEM_MESSAGE_COLOR,
        help="Color for system messages.",
    ),
    user_input_color: str = typer.Option(DEFAULT_INPUT_COLOR, help="Color for user input."),
    assistant_color: str = typer.Option(
        DEFAULT_ASSISTANT_COLOR,
        help="Color for assistant output.",
    ),
    warning_color: str = typer.Option(DEFAULT_WARNING_COLOR, help="Color for warning messages."),
    internal_thought_color: str = typer.Option(
        DEFAULT_INTERNAL_THOUGHT_COLOR,
        help="Color for internal thought messages.",
    ),
    chat_model: str = typer.Option(
        DEFAULT_CHAT_MODEL_NAME,
        help="The model to use for chat completions.",
    ),
    emedding_model: str = typer.Option(
        DEFAULT_EMBEDDING_MODEL_NAME,
        help="The model to use for text embeddings.",
    ),
    embedding_model_size: int = typer.Option(
        EMBEDDING_SIZE,
        help="The size of the embedding model.",
    ),
    debug: bool = typer.Option(
        False,
        help="Whether to fail fast when errors occur, and emit more verbose logging. Intended as a dev aid.",
    ),
):
    """Common parameters."""

    if not postgres_url and not use_docker_postgres:
        raise typer.BadParameter("If postgres_url parameter or ELROY_POSTGRES_URL env var is not set, use_docker_postgres must be True.")

    if postgres_url and use_docker_postgres:
        logging.info("postgres_url is set, ignoring use_docker_postgres set to True")

    ctx.obj = {
        "elroy_config": get_config(
            postgres_url=postgres_url or DOCKER_DB_URL,
            chat_model_name=chat_model,
            debug_mode=debug,
            embedding_model_name=emedding_model,
            embedding_model_size=embedding_model_size,
            context_window_token_limit=context_window_token_limit,
            openai_api_key=openai_api_key,
            anthropic_api_key=anthropic_api_key,
            openai_api_base=openai_api_base,
            openai_embedding_api_base=openai_embedding_api_base,
            openai_organization=openai_organization,
        ),
        "show_internal_thought_monologue": show_internal_thought_monologue,
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
def list_chat_models(ctx: typer.Context):
    """Lists supported chat models"""

    for m in open_ai_chat_completion_models:
        print(f"{m} (OpenAI)")
    for m in anthropic_models:
        print(f"{m} (Anthropic)")


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
        _print_memory_panel(context, get_context_messages(context))
        process_and_deliver_msg(context, "Elroy user {name} has been onboarded. Say hello and introduce yourself.", role=SYSTEM)
        context_messages = get_context_messages(context)

    else:
        context_messages = get_context_messages(context)

        validated_messages = validate(context.config, context_messages)

        if context_messages != validated_messages:
            replace_context_messages(context, validated_messages)
            logging.warning("Context messages were repaired")
            context_messages = get_context_messages(context)

        _print_memory_panel(context, context_messages)

        if (get_time_since_most_recent_user_message(context_messages) or timedelta()) < MIN_CONVO_AGE_FOR_GREETING:
            logging.info("User has interacted recently, skipping greeting.")

        else:
            get_user_preferred_name(context)

            # TODO: should include some information about how long the user has been talking to Elroy
            process_and_deliver_msg(
                context,
                get_user_logged_in_message(context),
                SYSTEM,
            )

    while True:
        try:
            context.io.update_completer(get_completer(context, context_messages))

            user_input = await context.io.prompt_user()
            if user_input.lower().startswith("/exit") or user_input == "exit":
                break
            elif user_input:
                process_and_deliver_msg(context, user_input)
                run_in_background_thread(contemplate, context)
        except EOFError:
            break

        context.io.rule()
        context_messages = get_context_messages(context)
        _print_memory_panel(context, context_messages)


def _print_memory_panel(context: ElroyContext, context_messages: Iterable[ContextMessage]) -> None:
    pipe(
        context_messages,
        filter(
            lambda m: not m.created_at
            or m.created_at > get_utc_now() - timedelta(seconds=context.config.max_in_context_message_age_seconds)
        ),
        map(lambda m: m.memory_metadata),
        filter(lambda m: m is not None),
        concat,
        map(lambda m: f"{m.memory_type}: {m.name}"),
        unique,
        list,
        sorted,
        context.io.print_memory_panel,
    )


def main():
    if len(sys.argv) == 1:
        sys.argv.append("chat")
    app()


if __name__ == "__main__":
    main()
