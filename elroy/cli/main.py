import asyncio
import logging
import os
import sys
from typing import Optional

import typer
from sqlalchemy import text
from sqlmodel import Session, create_engine

from ..cli.updater import ensure_current_db_migration
from ..config.config import ElroyConfig, get_config, session_manager
from ..config.constants import (
    DEFAULT_USER_TOKEN,
    LIST_MODELS_FLAG,
    MODEL_SELECTION_CONFIG_PANEL,
)
from ..io.base import StdIO
from ..io.cli import CliIO
from ..logging_config import setup_logging
from ..onboard_user import get_or_create_user
from ..repository.user import is_user_exists
from .chat import process_and_deliver_msg
from .context import init_elroy_context
from .info import handle_list_models, handle_version_check
from .options import CHAT_MODEL_ALIASES, CliOption
from .remember import handle_remember_file, handle_remember_stdin

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
    token: str = typer.Option(
        DEFAULT_USER_TOKEN,
        "--token",
        "-t",
        help="User token",
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
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    embedding_model: str = CliOption(
        "embedding_model",
        help="The model to use for text embeddings.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    embedding_model_size: int = CliOption(
        "embedding_model_size",
        help="The size of the embedding model.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    enable_caching: bool = CliOption(
        "enable_caching",
        help="Whether to enable caching for the LLM, both for embeddings and completions.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
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
        callback=handle_remember_file,
        is_eager=True,
    ),
    list_models: bool = typer.Option(
        False,
        LIST_MODELS_FLAG,
        help="Lists supported chat models and exits",
        rich_help_panel="Commands",
        callback=handle_list_models,
        is_eager=True,
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
        callback=handle_version_check,
        is_eager=True,
    ),
    sonnet: bool = CHAT_MODEL_ALIASES["sonnet"].get_typer_option(),
    opus: bool = CHAT_MODEL_ALIASES["opus"].get_typer_option(),
    gpt4o: bool = CHAT_MODEL_ALIASES["4o"].get_typer_option(),
    gpt4o_mini: bool = CHAT_MODEL_ALIASES["4o-mini"].get_typer_option(),
    o1: bool = CHAT_MODEL_ALIASES["o1"].get_typer_option(),
    o1_mini: bool = CHAT_MODEL_ALIASES["o1-mini"].get_typer_option(),
):
    """Common parameters."""
    validate_and_configure_db(postgres_url)
    assert postgres_url

    for k, v in locals().items():
        alias = k.replace("-", "_")
        if CHAT_MODEL_ALIASES.get(alias, None) and v:
            chat_model = CHAT_MODEL_ALIASES[alias].resolver()
            logging.info(f"Resolved model alias {alias} to {chat_model}")
            break

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

    setup_logging(config.log_file_path)

    with session_manager(config.postgres_url) as session:
        if remember_file or not sys.stdin.isatty():
            io = StdIO()

        else:
            io = CliIO(
                show_internal_thought_monologue,
                system_message_color,
                assistant_color,
                user_input_color,
                warning_color,
                internal_thought_color,
            )

            if not is_user_exists(session, token) and chat:
                pass

            user_id = get_or_create_user(session, io, config, token)

            with init_elroy_context(config, io, session, user_id) as context:
                if remember_file:
                    handle_remember_file(context, remember_file)
                elif remember:
                    handle_remember_stdin(context)
                else:  # default to chat
                    asyncio.run(process_and_deliver_msg(context, sys.stdin.read()))
                    raise typer.Exit()
        # else:

        #     with init_elroy_context(config, io, session, token) as context:
        #         if remember:
        #             handle_memory_interactive(context)
        #         else:
        #             check_updates()

        #             asyncio.run(handle_interactive_chat(context))


def validate_and_configure_db(postgres_url: Optional[str]):
    if not postgres_url:
        raise typer.BadParameter(
            "Postgres URL is required, please either set the ELROY_POSRTGRES_URL environment variable or run with --postgres-url"
        )

    # Check database connectivity
    if not check_db_connectivity(postgres_url):
        raise typer.BadParameter("Could not connect to database. Please check if database is running and connection URL is correct.")

    """Configure the database"""
    ensure_current_db_migration(postgres_url)


def get_config_typer(ctx: typer.Context) -> ElroyConfig:

    p = ctx.params

    return get_config(
        postgres_url=p["postgres_url"],
        chat_model_name=p["chat_model"],
        debug=p["debug"],
        embedding_model=p["embedding_model"],
        embedding_model_size=p["embedding_model_size"],
        context_refresh_trigger_tokens=p["context_refresh_trigger_tokens"],
        context_refresh_target_tokens=p["context_refresh_target_tokens"],
        max_context_age_minutes=p["max_context_age_minutes"],
        context_refresh_interval_minutes=p["context_refresh_interval_minutes"],
        min_convo_age_for_greeting_minutes=p["min_convo_age_for_greeting_minutes"],
        l2_memory_relevance_distance_threshold=p["l2_memory_relevance_distance_threshold"],
        l2_memory_consolidation_distance_threshold=p["l2_memory_consolidation_distance_threshold"],
        initial_context_refresh_wait_seconds=p["initial_context_refresh_wait_seconds"],
        openai_api_key=p["openai_api_key"],
        anthropic_api_key=p["anthropic_api_key"],
        openai_api_base=p["openai_api_base"],
        openai_embedding_api_base=p["openai_embedding_api_base"],
        openai_organization=p["openai_organization"],
        log_file_path=p["os.path.abspath(log_file_path)"],
        enable_caching=p["enable_caching"],
    )


if __name__ == "__main__":
    app()
