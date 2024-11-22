import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

import typer
from click import get_current_context
from colorama import init
from litellm import anthropic_models, open_ai_chat_completion_models
from toolz import concat, pipe, unique
from toolz.curried import filter, map
from typer import Option

from ..cli.updater import check_updates, version_callback
from ..config.config import ElroyContext, get_config, load_defaults
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


def CliOption(yaml_key: str, *args: Any, **kwargs: Any):
    """
    Creates a typer Option with value priority:
    1. CLI provided value (handled by typer)
    2. User config file value (if provided)
    3. defaults.yml value
    """

    def get_default():
        ctx = get_current_context()
        config_file = ctx.params.get("config_file")
        defaults = load_defaults(config_file)
        return defaults.get(yaml_key)

    return Option(*args, default_factory=get_default, **kwargs)


@app.callback()
def common(
    # Basic Configuration
    ctx: typer.Context,
    config_file: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML configuration file. Values override defaults but are overridden by explicit flags or environment variables.",
        rich_help_panel="Basic Configuration",
    ),
    version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
        rich_help_panel="Basic Configuration",
    ),
    debug: bool = CliOption(
        "debug",
        help="Whether to fail fast when errors occur, and emit more verbose logging.",
        rich_help_panel="Basic Configuration",
    ),
    # Database Configuration
    postgres_url: Optional[str] = CliOption(
        "postgres_url",
        envvar="ELROY_POSTGRES_URL",
        help="Postgres URL to use for Elroy. If set, overrides use_docker_postgres.",
        rich_help_panel="Database Configuration",
    ),
    use_docker_postgres: Optional[bool] = CliOption(
        "use_docker_postgres",
        envvar="USE_DOCKER_POSTGRES",
        help="If true and postgres_url is not set, will attempt to start a Docker container for Postgres.",
        rich_help_panel="Database Configuration",
    ),
    stop_docker_postgres_on_exit: Optional[bool] = CliOption(
        "stop_docker_postgres_on_exit",
        envvar="STOP_DOCKER_POSTGRES_ON_EXIT",
        help="Whether or not to stop the Postgres container on exit.",
        rich_help_panel="Database Configuration",
    ),
    # API Configuration
    openai_api_key: Optional[str] = CliOption(
        "openai_api_key",
        envvar="OPENAI_API_KEY",
        help="OpenAI API key, required for OpenAI (or OpenAI compatible) models.",
        rich_help_panel="API Configuration",
    ),
    openai_api_base: Optional[str] = CliOption(
        "openai_api_base",
        envvar="OPENAI_API_BASE",
        help="OpenAI API (or OpenAI compatible) base URL.",
        rich_help_panel="API Configuration",
    ),
    openai_embedding_api_base: Optional[str] = CliOption(
        "openai_embedding_api_base",
        envvar="OPENAI_API_BASE",
        help="OpenAI API (or OpenAI compatible) base URL for embeddings.",
        rich_help_panel="API Configuration",
    ),
    openai_organization: Optional[str] = CliOption(
        "openai_organization",
        envvar="OPENAI_ORGANIZATION",
        help="OpenAI (or OpenAI compatible) organization ID.",
        rich_help_panel="API Configuration",
    ),
    anthropic_api_key: Optional[str] = CliOption(
        "anthropic_api_key",
        envvar="ANTHROPIC_API_KEY",
        help="Anthropic API key, required for Anthropic models.",
        rich_help_panel="API Configuration",
    ),
    # Model Configuration
    chat_model: str = CliOption(
        "chat_model",
        envvar="ELROY_CHAT_MODEL",
        help="The model to use for chat completions.",
        rich_help_panel="Model Configuration",
    ),
    emedding_model: str = CliOption(
        "embedding_model",
        help="The model to use for text embeddings.",
        rich_help_panel="Model Configuration",
    ),
    embedding_model_size: int = CliOption(
        "embedding_model_size",
        help="The size of the embedding model.",
        rich_help_panel="Model Configuration",
    ),
    # Context Management
    context_refresh_trigger_tokens: int = CliOption(
        "context_refresh_trigger_tokens",
        help="Number of tokens that triggers a context refresh and compresion of messages in the context window.",
        rich_help_panel="Context Management",
    ),
    context_refresh_target_tokens: int = CliOption(
        "context_refresh_target_tokens",
        help="Target number of tokens after context refresh / context compression, how many tokens to aim to keep in context.",
        rich_help_panel="Context Management",
    ),
    max_context_age_minutes: float = CliOption(
        "max_context_age_minutes",
        help="Maximum age in minutes to keep. Messages older tha this will be dropped from context, regardless of token limits",
        rich_help_panel="Context Management",
    ),
    context_refresh_interval_minutes: float = CliOption(
        "context_refresh_interval_minutes",
        help="How often in minutes to refresh system message and compress context.",
        rich_help_panel="Context Management",
    ),
    min_convo_age_for_greeting_minutes: float = CliOption(
        "min_convo_age_for_greeting_minutes",
        help="Minimum age in minutes of conversation before the assistant will offer a greeting on login.",
        rich_help_panel="Context Management",
    ),
    # Memory Management
    l2_memory_relevance_distance_threshold: float = CliOption(
        "l2_memory_relevance_distance_threshold",
        help="L2 distance threshold for memory relevance.",
        rich_help_panel="Memory Management",
    ),
    l2_memory_consolidation_distance_threshold: float = CliOption(
        "l2_memory_consolidation_distance_threshold",
        help="L2 distance threshold for memory consolidation.",
        rich_help_panel="Memory Management",
    ),
    initial_context_refresh_wait_seconds: int = CliOption(
        "initial_context_refresh_wait_seconds",
        help="Initial wait time in seconds after login before the initial context refresh and compression.",
        rich_help_panel="Memory Management",
    ),
    # UI Configuration
    show_internal_thought_monologue: bool = CliOption(
        "show_internal_thought_monologue",
        help="Show the assistant's internal thought monologue like memory consolidation and internal reflection.",
        rich_help_panel="UI Configuration",
    ),
    system_message_color: str = CliOption(
        "system_message_color",
        help="Color for system messages.",
        rich_help_panel="UI Configuration",
    ),
    user_input_color: str = CliOption(
        "user_input_color",
        help="Color for user input.",
        rich_help_panel="UI Configuration",
    ),
    assistant_color: str = CliOption(
        "assistant_color",
        help="Color for assistant output.",
        rich_help_panel="UI Configuration",
    ),
    warning_color: str = CliOption(
        "warning_color",
        help="Color for warning messages.",
        rich_help_panel="UI Configuration",
    ),
    internal_thought_color: str = CliOption(
        "internal_thought_color",
        help="Color for internal thought messages.",
        rich_help_panel="UI Configuration",
    ),
    # Logging
    log_file_path: str = CliOption(
        "log_file_path",
        envvar="ELROY_LOG_FILE_PATH",
        help="Where to write logs.",
        rich_help_panel="Logging",
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
            debug=debug,
            embedding_model=emedding_model,
            embedding_model_size=embedding_model_size,
            context_refresh_trigger_tokens=context_refresh_trigger_tokens,
            context_refresh_target_tokens=context_refresh_target_tokens,
            max_context_age_minutes=max_context_age_minutes,
            context_refresh_interval_minutes=context_refresh_interval_minutes,
            min_convo_age_for_greeting_minutes=min_convo_age_for_greeting_minutes,
            l2_memory_relevance_distance_threshold=l2_memory_relevance_distance_threshold,
            l2_memory_consolidation_distance_threshold=l2_memory_consolidation_distance_threshold,
            initial_context_refresh_wait_seconds=initial_context_refresh_wait_seconds,
            openai_api_key=openai_api_key,
            anthropic_api_key=anthropic_api_key,
            openai_api_base=openai_api_base,
            openai_embedding_api_base=openai_embedding_api_base,
            openai_organization=openai_organization,
            log_file_path=log_file_path,
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


@app.command()
def show_config(ctx: typer.Context):
    """Shows current configuration (for testing)"""
    config = ctx.obj["elroy_config"]
    for key, value in config.__dict__.items():
        print(f"{key}={value}")


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
        context.config.context_refresh_interval,
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

        if (get_time_since_most_recent_user_message(context_messages) or timedelta()) < context.config.min_convo_age_for_greeting:
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


def main():
    if len(sys.argv) == 1:
        sys.argv.append("chat")
    app()


if __name__ == "__main__":
    main()
