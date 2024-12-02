import asyncio
import logging
import os
import sys
from typing import Optional

import typer
from sqlalchemy import text
from sqlmodel import Session, create_engine

from .options import CHAT_MODEL_ALIASES, CliOption, get_cli_option


def generate_model_options():
    """Generate model options for CLI parameters"""
    options = []
    for alias_key, alias in CHAT_MODEL_ALIASES.items():
        option_name = f"--{alias_key}"  # Keep the original hyphenated name
        options.append(typer.Option(False, option_name, help=f"Use {alias.description}", rich_help_panel="Model Selection"))
    return options


from ..cli.updater import check_updates, handle_version_check
from ..config.config import get_config
from ..config.constants import LIST_MODELS_FLAG
from ..io.base import StdIO
from ..io.cli import CliIO
from .chat import handle_chat, process_and_deliver_msg
from .context import init_elroy_context
from .remember import (
    handle_memory_interactive,
    handle_remember_file,
    handle_remember_stdin,
)

app = typer.Typer(
    help="Elroy CLI",
    context_settings={"obj": {}},
    no_args_is_help=False,  # Don't show help when no args provided
    callback=None,  # Important - don't use a default command
)


def check_db_connectivity(postgres_url: str) -> bool:
    """Check if database is reachable by running a simple query"""
    try:
        with Session(create_engine(postgres_url)) as session:
            session.exec(text("SELECT 1")).first()  # type: ignore
            return True
    except Exception as e:
        logging.error(f"Database connectivity check failed: {e}")
        return False


@app.callback(invoke_without_command=True)
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
    debug: bool = CliOption(
        "debug",
        help="Whether to fail fast when errors occur, and emit more verbose logging.",
        rich_help_panel="Basic Configuration",
    ),
    # Database Configuration
    postgres_url: Optional[str] = CliOption(
        "postgres_url",
        envvar="ELROY_POSTGRES_URL",
        help="Postgres URL to use for Elroy.",
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
    embedding_model: str = CliOption(
        "embedding_model",
        help="The model to use for text embeddings.",
        rich_help_panel="Model Configuration",
    ),
    embedding_model_size: int = CliOption(
        "embedding_model_size",
        help="The size of the embedding model.",
        rich_help_panel="Model Configuration",
    ),
    enable_caching: bool = CliOption(
        "enable_caching",
        help="Whether to enable caching for the LLM, both for embeddings and completions.",
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
    # Commmands
    chat: bool = typer.Option(
        False,
        "--chat",
        help="Opens an interactive chat session, or generates a response to stdin input. THe default command.",
        rich_help_panel="Commands",
    ),
    remember: bool = typer.Option(
        False,
        "--remember",
        "-r",
        help="Create a new memory from stdin or interactively",
        rich_help_panel="Commands",
    ),
    remember_file: Optional[str] = typer.Option(
        None,
        "--remember-file",
        "-f",
        help="File to read memory text from when using --remember",
        rich_help_panel="Commands",
    ),
    list_models: bool = typer.Option(
        False,
        LIST_MODELS_FLAG,
        help="Lists supported chat models and exits",
        rich_help_panel="Commands",
    ),
    show_config: bool = typer.Option(
        False,
        "--show-config",
        help="Shows current configuration and exits.",
        rich_help_panel="Commands",
    ),
    version: bool = typer.Option(
        None,
        "--version",
        help="Show version and exit.",
        rich_help_panel="Commands",
    ),
    gpt4o: bool = get_cli_option("4o"),
    gpt4o_mini: bool = get_cli_option("4o-mini"),
    sonnet: bool = get_cli_option("sonnet"),
    opus: bool = get_cli_option("opus"),
    o1: bool = get_cli_option("o1"),
    o1_mini: bool = get_cli_option("o1-mini"),
):
    """Common parameters."""

    if version:
        handle_version_check()

    if list_models:
        from litellm import anthropic_models, open_ai_chat_completion_models

        for m in open_ai_chat_completion_models:
            print(f"{m} (OpenAI)")
        for m in anthropic_models:
            print(f"{m} (Anthropic)")
        exit(0)

    if not postgres_url:
        raise typer.BadParameter(
            "Postgres URL is required, please either set the ELROY_POSRTGRES_URL environment variable or run with --postgres-url"
        )

    if gpt4o:
        chat_model = CHAT_MODEL_ALIASES["4o"].resolver()
    elif gpt4o_mini:
        chat_model = CHAT_MODEL_ALIASES["4o-mini"].resolver()
    elif sonnet:
        chat_model = CHAT_MODEL_ALIASES["sonnet"].resolver()
    elif opus:
        chat_model = CHAT_MODEL_ALIASES["opus"].resolver()
    elif o1:
        chat_model = CHAT_MODEL_ALIASES["o1"].resolver()
    elif o1_mini:
        chat_model = CHAT_MODEL_ALIASES["o1-mini"].resolver()

    config = get_config(
        postgres_url=postgres_url,
        chat_model_name=chat_model,
        debug=debug,
        embedding_model=embedding_model,
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
        log_file_path=os.path.abspath(log_file_path),
        enable_caching=enable_caching,
    )

    if show_config:
        for key, value in config.__dict__.items():
            print(f"{key}={value}")
        raise typer.Exit()

    # Check database connectivity
    if not check_db_connectivity(postgres_url):
        raise typer.BadParameter("Could not connect to database. Please check if database is running and connection URL is correct.")

    if remember_file or not sys.stdin.isatty():
        io = StdIO()

        with init_elroy_context(config, io) as context:
            if remember_file:
                handle_remember_file(context, remember_file)
            elif remember:
                handle_remember_stdin(context)
            else:  # default to chat
                asyncio.run(process_and_deliver_msg(context, sys.stdin.read()))
                raise typer.Exit()
    else:
        io = CliIO(
            show_internal_thought_monologue,
            system_message_color,
            assistant_color,
            user_input_color,
            warning_color,
            internal_thought_color,
        )
        with init_elroy_context(config, io) as context:
            if remember:
                handle_memory_interactive(context)
            else:
                check_updates()
                asyncio.run(handle_chat(context))


if __name__ == "__main__":
    app()
