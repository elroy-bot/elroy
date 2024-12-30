import asyncio
import logging
import sys
from datetime import datetime
from typing import Optional

import click
import typer
from toolz import merge, pipe
from toolz.curried import keyfilter

from ..config.constants import CONFIG_FILE_KEY, MODEL_SELECTION_CONFIG_PANEL
from ..config.ctx import ElroyContext, elroy_context, with_db
from ..config.paths import get_default_config_path, get_default_sqlite_url
from ..io.base import StdIO
from ..io.cli import CliIO
from ..llm.persona import get_persona
from ..repository.memory import manually_record_user_memory
from ..repository.user import get_user_id_if_exists
from ..tools.developer import print_elroy_config
from ..tools.user_preferences import reset_system_persona, set_system_persona
from ..utils.utils import datetime_to_string
from .bug_report import create_bug_report_from_exception_if_confirmed
from .chat import (
    handle_message_interactive,
    handle_message_stdio,
    onboard_interactive,
    run_chat,
)
from .options import CliOption, get_config_params, resolve_model_alias
from .updater import check_latest_version

MODEL_ALIASES = ["sonnet", "opus", "gpt4o", "gpt4o_mini", "o1", "o1_mini"]

app = typer.Typer(
    help="Elroy CLI",
    context_settings={
        "obj": {},
    },
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def common(
    ctx: typer.Context,
    config_file: str = typer.Option(
        get_default_config_path(),
        "--config",
        envvar="ELROY_CONFIG_FILE",
        help="Path to YAML configuration file. Values override defaults but are overridden by explicit flags or environment variables.",
        rich_help_panel="Basic Configuration",
    ),
    default_assistant_name: str = CliOption(
        "default_assistant_name",
        help="Default name for the assistant.",
        rich_help_panel="Basic Configuration",
    ),
    debug: bool = CliOption(
        "debug",
        help="Whether to fail fast when errors occur, and emit more verbose logging.",
        rich_help_panel="Basic Configuration",
    ),
    user_token: str = CliOption(
        "user_token",
        help="User token to use for Elroy",
        rich_help_panel="Basic Configuration",
    ),
    # Database Configuration
    database_url: Optional[str] = typer.Option(
        get_default_sqlite_url(),
        envvar="ELROY_DATABASE_URL",
        help="Valid SQLite or Postgres URL for the database. If Postgres, the pgvector extension must be installed.",
        rich_help_panel="Basic Configuration",
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
    enable_tools: bool = typer.Option(
        True,
        "--enable-tools",
        help="Whether to enable tool calls for the assistant",
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
    min_convo_age_for_greeting_minutes: Optional[float] = CliOption(
        "min_convo_age_for_greeting_minutes",
        help="Minimum age in minutes of conversation before the assistant will offer a greeting on login. 0 means assistant will offer greeting each time. To disable greeting, set enable_assistant_greeting=False (This will override any value for min_convo_age_for_greeting_minutes)",
        rich_help_panel="Context Management",
    ),
    enable_assistant_greeting: bool = CliOption(
        "enable_assistant_greeting",
        help="Whether to allow the assistant to send the first message",
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
    show_internal_thought: bool = CliOption(
        "show_internal_thought",
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
        help="Where to write logs.",
        rich_help_panel="Logging",
    ),
    tool: str = typer.Option(
        None,
        "--tool",
        "-t",
        help="Specifies the tool to use in responding to a message. Only valid when processing a single message",
    ),
    sonnet: bool = typer.Option(
        False,
        help="Use Anthropic's Sonnet model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    opus: bool = typer.Option(
        False,
        help="Use Anthropic's Opus model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    gpt4o: bool = typer.Option(
        False,
        help="Use OpenAI's GPT-4o model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    gpt4o_mini: bool = typer.Option(
        False,
        help="Use OpenAI's GPT-4o-mini model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    o1: bool = typer.Option(
        False,
        help="Use OpenAI's o1 model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    o1_mini: bool = typer.Option(
        False,
        help="Use OpenAI's o1-mini model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
):
    """Common parameters."""

    # ctx.params["parent"] = ctx

    if ctx.invoked_subcommand is None:
        ctx.params["command"] = click.Command("chat")
    else:
        ctx.params["command"] = ctx.command

    for m in MODEL_ALIASES:
        if ctx.params.get(m):
            ctx.params["chat_model"] = resolve_model_alias(m)

    ctx.obj = pipe(
        ctx.params,
        lambda x: merge(get_config_params(ctx.params.get(CONFIG_FILE_KEY)), x),
        keyfilter(lambda k: k not in MODEL_ALIASES),
        dict,
        lambda x: ElroyContext(parent=ctx, **x),
    )

    if ctx.invoked_subcommand is None:
        chat(ctx.obj)


@app.command(name="chat")
@elroy_context
@with_db
def chat(ctx: ElroyContext):
    """Opens an interactive chat session."""
    if sys.stdin.isatty():
        try:
            if not get_user_id_if_exists(ctx.db, ctx.user_token):
                asyncio.run(onboard_interactive(ctx))
            asyncio.run(run_chat(ctx))
        except Exception as e:
            create_bug_report_from_exception_if_confirmed(ctx, e)
    else:
        message = sys.stdin.read()
        handle_message_stdio(ctx, StdIO(), message, ctx.tool)


@app.command(name="message")
@elroy_context
@with_db
def message(
    ctx: ElroyContext,
    message: Optional[str] = typer.Argument(..., help="The message to process"),
    tool: str = typer.Option(None, "--tool", "-t", help="Specifies the tool to use in responding to a message"),
):
    """Process a single message and exit."""
    if sys.stdin.isatty() and not message:
        io = ctx.io
        assert isinstance(io, CliIO)
        handle_message_interactive(ctx, io, tool)
    else:
        assert message
        handle_message_stdio(ctx, StdIO(), message, tool)


@app.command(name="remember")
@elroy_context
@with_db
def remember(
    ctx: ElroyContext,
    text: Optional[str] = typer.Argument(
        None,
        help="Text to remember. If not provided, will prompt interactively",
    ),
):
    """Create a new memory from text or interactively."""

    if not get_user_id_if_exists(ctx.db, ctx.user_token):
        ctx.io.notify_warning("Creating memory for new user")

    if text:
        memory_name = f"Memory from CLI, created {datetime_to_string(datetime.now())}"
        manually_record_user_memory(ctx, text, memory_name)
        ctx.io.sys_message(f"Memory created: {memory_name}")
        raise typer.Exit()

    elif sys.stdin.isatty():
        io = ctx.io
        assert isinstance(io, CliIO)
        memory_text = asyncio.run(io.prompt_user("Enter the memory text:"))
        memory_text += f"\nManually entered memory, at: {datetime_to_string(datetime.now())}"
        # Optionally get memory name
        memory_name = asyncio.run(io.prompt_user("Enter memory name (optional, press enter to skip):"))
        try:
            manually_record_user_memory(ctx, memory_text, memory_name)
            ctx.io.sys_message(f"Memory created: {memory_name}")
            raise typer.Exit()
        except ValueError as e:
            ctx.io.assistant_msg(f"Error creating memory: {e}")
            raise typer.Exit(1)
    else:
        memory_text = sys.stdin.read()
        metadata = "Memory ingested from stdin\n" f"Ingested at: {datetime_to_string(datetime.now())}\n"
        memory_text = f"{metadata}\n{memory_text}"
        memory_name = f"Memory from stdin, ingested {datetime_to_string(datetime.now())}"
        manually_record_user_memory(ctx, memory_text, memory_name)
        ctx.io.sys_message(f"Memory created: {memory_name}")
        raise typer.Exit()


@app.command(name="list-models")
def list_models():
    """Lists supported chat models and exits."""
    from ..config.models import (
        get_supported_anthropic_models,
        get_supported_openai_models,
    )

    for m in get_supported_openai_models():
        print(f"{m} (OpenAI)")
    for m in get_supported_anthropic_models():
        print(f"{m} (Anthropic)")
    raise typer.Exit()


@app.command(name="show-config")
@elroy_context
@with_db
def show_config(ctx: ElroyContext):
    """Shows current configuration and exits."""
    print(print_elroy_config(ctx))


@app.command()
def version():
    """Show version and exit."""
    current_version, latest_version = check_latest_version()
    if latest_version > current_version:
        typer.echo(f"Elroy version: {current_version} (newer version {latest_version} available)")
        typer.echo("\nTo upgrade, run:")
        typer.echo(f"    pip install --upgrade elroy=={latest_version}")
    else:
        typer.echo(f"Elroy version: {current_version} (up to date)")

    raise typer.Exit()


@app.command(name="set-persona")
@elroy_context
@with_db
def set_persona(ctx: ElroyContext, persona: str = typer.Argument(..., help="Persona text to set")):
    """Set a custom persona for the assistant."""
    if get_user_id_if_exists(ctx.db, ctx.user_token):
        logging.info(f"No user found for token {ctx.user_token}, creating one")
    set_system_persona(ctx, persona)
    raise typer.Exit()


@app.command(name="reset-persona")
@elroy_context
@with_db
def reset_persona(ctx: ElroyContext):
    """Removes any custom persona, reverting to the default."""
    if not get_user_id_if_exists(ctx.db, ctx.user_token):
        logging.warning(f"No user found for token {ctx.user_token}, so no persona to clear")
        return typer.Exit()
    else:
        reset_system_persona(ctx)
    raise typer.Exit()


@app.command(name="show-persona")
@elroy_context
@with_db
def show_persona(ctx: ElroyContext):
    """Print the system persona and exit."""
    print(get_persona(ctx))
    raise typer.Exit()


if __name__ == "__main__":
    app()
