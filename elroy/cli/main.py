import asyncio
import logging
import sys
from bdb import BdbQuit
from datetime import datetime
from typing import List, Optional

import typer

from ..config.constants import MODEL_SELECTION_CONFIG_PANEL
from ..config.ctx import ElroyContext, get_ctx
from ..config.paths import get_default_config_path, get_default_sqlite_url
from ..io.base import StdIO
from ..io.cli import CliIO
from ..llm.persona import get_persona
from ..logging_config import setup_logging
from ..repository.memories.consolidation import consolidate_memories
from ..repository.memories.operations import manually_record_user_memory
from ..repository.user import get_user_id_if_exists
from ..system_commands import query_memory
from ..tools.developer import do_print_config
from ..tools.user_preferences import reset_system_persona
from ..tools.user_preferences import set_persona as do_set_persona
from ..utils.utils import datetime_to_string
from .bug_report import create_bug_report_from_exception_if_confirmed
from .chat import (
    handle_message_interactive,
    handle_message_stdio,
    onboard_interactive,
    run_chat,
)
from .options import ElroyOption, get_resolved_params, resolve_model_alias
from .updater import check_latest_version, check_updates

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
    typer_ctx: typer.Context,
    config_path: str = typer.Option(
        get_default_config_path(),
        "--config",
        envvar="ELROY_CONFIG_FILE",
        help="Path to YAML configuration file. Values override defaults but are overridden by explicit flags or environment variables.",
        rich_help_panel="Basic Configuration",
    ),
    default_assistant_name: str = ElroyOption(
        "default_assistant_name",
        help="Default name for the assistant.",
        rich_help_panel="Basic Configuration",
    ),
    debug: bool = ElroyOption(
        "debug",
        help="Whether to fail fast when errors occur, and emit more verbose logging.",
        rich_help_panel="Basic Configuration",
    ),
    user_token: str = ElroyOption(
        "user_token",
        help="User token to use for Elroy",
        rich_help_panel="Basic Configuration",
    ),
    custom_tools_path: List[str] = typer.Option(
        [],
        "--custom-tools-path",
        help="Path to custom functions to load",
        show_default=False,
        rich_help_panel="Basic Configuration",
    ),
    # Database Configuration
    database_url: Optional[str] = ElroyOption(
        "database_url",
        default_factory=get_default_sqlite_url,
        help="Valid SQLite or Postgres URL for the database. If Postgres, the pgvector extension must be installed.",
        rich_help_panel="Basic Configuration",
    ),
    # API Configuration
    openai_api_key: Optional[str] = ElroyOption(
        "openai_api_key",
        help="OpenAI API key, required for OpenAI (or OpenAI compatible) models.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    openai_api_base: Optional[str] = ElroyOption(
        "openai_api_base",
        help="OpenAI API (or OpenAI compatible) base URL.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    openai_embedding_api_base: Optional[str] = ElroyOption(
        "openai_embedding_api_base",
        help="OpenAI API (or OpenAI compatible) base URL for embeddings.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    openai_organization: Optional[str] = ElroyOption(
        "openai_organization",
        help="OpenAI (or OpenAI compatible) organization ID.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    anthropic_api_key: Optional[str] = ElroyOption(
        "anthropic_api_key",
        help="Anthropic API key, required for Anthropic models.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    # Model Configuration
    chat_model: str = ElroyOption(
        "chat_model",
        help="The model to use for chat completions.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    enable_tools: bool = ElroyOption(
        "enable-tools",
        help="Whether to enable tool calls for the assistant",
        rich_help_panel="Basic Configuration",
    ),
    inline_tool_calls: bool = ElroyOption(
        "inline_tool_calls",
        help="Whether to enable inline tool calls in the assistant (better for some open source models)",
        rich_help_panel="Basic Configuration",
    ),
    embedding_model: str = ElroyOption(
        "embedding_model",
        help="The model to use for text embeddings.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    embedding_model_size: int = ElroyOption(
        "embedding_model_size",
        help="The size of the embedding model.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    enable_caching: bool = ElroyOption(
        "enable_caching",
        help="Whether to enable caching for the LLM, both for embeddings and completions.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    # Context Management
    max_assistant_loops: int = ElroyOption(
        "max_assistant_loops",
        help="Maximum number of loops the assistant can run before tools are temporarily made unvailable (returning for the next user message).",
        rich_help_panel="Context Management",
    ),
    context_refresh_trigger_tokens: int = ElroyOption(
        "context_refresh_trigger_tokens",
        help="Number of tokens that triggers a context refresh and compresion of messages in the context window.",
        rich_help_panel="Context Management",
    ),
    context_refresh_target_tokens: int = ElroyOption(
        "context_refresh_target_tokens",
        help="Target number of tokens after context refresh / context compression, how many tokens to aim to keep in context.",
        rich_help_panel="Context Management",
    ),
    max_context_age_minutes: float = ElroyOption(
        "max_context_age_minutes",
        help="Maximum age in minutes to keep. Messages older tha this will be dropped from context, regardless of token limits",
        rich_help_panel="Context Management",
    ),
    context_refresh_interval_minutes: float = ElroyOption(
        "context_refresh_interval_minutes",
        help="How often in minutes to refresh system message and compress context.",
        rich_help_panel="Context Management",
    ),
    min_convo_age_for_greeting_minutes: Optional[float] = ElroyOption(
        "min_convo_age_for_greeting_minutes",
        help="Minimum age in minutes of conversation before the assistant will offer a greeting on login. 0 means assistant will offer greeting each time. To disable greeting, set enable_assistant_greeting=False (This will override any value for min_convo_age_for_greeting_minutes)",
        rich_help_panel="Context Management",
    ),
    enable_assistant_greeting: bool = ElroyOption(
        "enable_assistant_greeting",
        help="Whether to allow the assistant to send the first message",
        rich_help_panel="Context Management",
    ),
    # Memory Consolidation
    memories_between_consolidation: int = ElroyOption(
        "memories_between_consolidation",
        help="How many memories to create before triggering a memory consolidation operation.",
        rich_help_panel="Memory Consolidation",
    ),
    l2_memory_relevance_distance_threshold: float = ElroyOption(
        "l2_memory_relevance_distance_threshold",
        help="L2 distance threshold for memory relevance.",
        rich_help_panel="Memory Consolidation",
    ),
    memory_cluster_similarity_threshold: float = ElroyOption(
        "memory_cluster_similarity_threshold",
        help="Threshold for memory cluster similarity.",
        rich_help_panel="Memory Consolidation",
    ),
    max_memory_cluster_size: int = ElroyOption(
        "max_memory_cluster_size",
        help="The maximum number of memories that can be consolidated into a single memory at once.",
        rich_help_panel="Memory Consolidation",
    ),
    min_memory_cluster_size: int = ElroyOption(
        "min_memory_cluster_size",
        help="The minimum number of memories that can be consolidated into a single memory at once.",
        rich_help_panel="Memory Consolidation",
    ),
    initial_context_refresh_wait_seconds: int = ElroyOption(
        "initial_context_refresh_wait_seconds",
        help="Initial wait time in seconds after login before the initial context refresh and compression.",
        rich_help_panel="Memory Consolidation",
    ),
    # UI Configuration
    show_internal_thought: bool = ElroyOption(
        "show_internal_thought",
        help="Show the assistant's internal thought monologue like memory consolidation and internal reflection.",
        rich_help_panel="UI Configuration",
    ),
    system_message_color: str = ElroyOption(
        "system_message_color",
        help="Color for system messages.",
        rich_help_panel="UI Configuration",
    ),
    user_input_color: str = ElroyOption(
        "user_input_color",
        help="Color for user input.",
        rich_help_panel="UI Configuration",
    ),
    assistant_color: str = ElroyOption(
        "assistant_color",
        help="Color for assistant output.",
        rich_help_panel="UI Configuration",
    ),
    warning_color: str = ElroyOption(
        "warning_color",
        help="Color for warning messages.",
        rich_help_panel="UI Configuration",
    ),
    internal_thought_color: str = ElroyOption(
        "internal_thought_color",
        help="Color for internal thought messages.",
        rich_help_panel="UI Configuration",
    ),
    sonnet: bool = typer.Option(
        False,
        "--sonnet",
        help="Use Anthropic's Sonnet model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    opus: bool = typer.Option(
        False,
        "--opus",
        help="Use Anthropic's Opus model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    gpt4o: bool = typer.Option(
        False,
        "--4o",
        help="Use OpenAI's GPT-4o model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    gpt4o_mini: bool = typer.Option(
        False,
        "--4o-mini",
        help="Use OpenAI's GPT-4o-mini model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    o1: bool = typer.Option(
        False,
        "--o1",
        help="Use OpenAI's o1 model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    o1_mini: bool = typer.Option(
        False,
        "--o1-mini",
        help="Use OpenAI's o1-mini model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
):
    """Common parameters."""

    for m in MODEL_ALIASES:
        if typer_ctx.params.get(m):
            logging.info(f"Model alias {m} selected")
            resolved = resolve_model_alias(m)
            if not resolved:
                logging.warning("Model alias not found")
            else:
                typer_ctx.params["chat_model"] = resolved
        del typer_ctx.params[m]

    typer_ctx.obj = ElroyContext(
        **get_resolved_params(**typer_ctx.params),
    )

    setup_logging()

    if typer_ctx.invoked_subcommand is None:
        chat(typer_ctx)


@app.command(name="chat")
def chat(typer_ctx: typer.Context):
    """Opens an interactive chat session."""
    ctx = get_ctx(typer_ctx)
    with ctx.dbsession():
        if sys.stdin.isatty():
            check_updates()
            try:
                if not get_user_id_if_exists(ctx.db, ctx.user_token):
                    asyncio.run(onboard_interactive(ctx))
                asyncio.run(run_chat(ctx))
            except BdbQuit:
                logging.info("Exiting...")
            except EOFError:
                logging.info("Exiting...")
            except Exception as e:
                create_bug_report_from_exception_if_confirmed(ctx, e)
        else:
            message = sys.stdin.read()
            handle_message_stdio(ctx, StdIO(), message, None)


@app.command(name="query")
def query(
    typer_ctx: typer.Context,
    prompt: str = typer.Argument(..., help="The prompt to query the Elroy with"),
):
    """Searches memory with the given prompt, returns the response."""
    ctx = get_ctx(typer_ctx)
    with ctx.dbsession():
        ctx.io.print(query_memory(ctx, prompt))


@app.command(name="message")
def message(
    typer_ctx: typer.Context,
    message: Optional[str] = typer.Argument(..., help="The message to process"),
    tool: str = typer.Option(
        None,
        "--tool",
        "-t",
        help="Specifies the tool to use in responding to a message",
    ),
):
    """Process a single message and exit."""
    ctx = get_ctx(typer_ctx)
    with ctx.dbsession():
        if sys.stdin.isatty() and not message:
            io = ctx.io
            assert isinstance(io, CliIO)
            handle_message_interactive(ctx, io, tool)
        else:
            assert message
            handle_message_stdio(ctx, StdIO(), message, tool)


@app.command(name="print-tools")
def print_tools(
    typer_ctx: typer.Context,
    tool: Optional[str] = typer.Argument(None, help="Tool to print schema for"),
):
    """Prints the schema for a tool and exits."""
    ctx = get_ctx(typer_ctx)
    ctx.io.print(ctx.tool_registry.get_schemas())  # type: ignore


@app.command(name="remember")
def remember(
    typer_ctx: typer.Context,
    text: Optional[str] = typer.Argument(
        None,
        help="Text to remember. If not provided, will prompt interactively",
    ),
):
    """Create a new memory from text or interactively."""
    ctx = get_ctx(typer_ctx)
    with ctx.dbsession():
        if not get_user_id_if_exists(ctx.db, ctx.user_token):
            ctx.io.warning("Creating memory for new user")

        if text:
            memory_name = f"Memory from CLI, created {datetime_to_string(datetime.now())}"
            manually_record_user_memory(ctx, text, memory_name)
            ctx.io.info(f"Memory created: {memory_name}")
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
                ctx.io.info(f"Memory created: {memory_name}")
                raise typer.Exit()
            except ValueError as e:
                ctx.io.warning(f"Error creating memory: {e}")
                raise typer.Exit(1)
        else:
            memory_text = sys.stdin.read()
            metadata = "Memory ingested from stdin\n" f"Ingested at: {datetime_to_string(datetime.now())}\n"
            memory_text = f"{metadata}\n{memory_text}"
            memory_name = f"Memory from stdin, ingested {datetime_to_string(datetime.now())}"
            manually_record_user_memory(ctx, memory_text, memory_name)
            ctx.io.info(f"Memory created: {memory_name}")
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


@app.command(name="print-config")
def print_config(
    typer_ctx: typer.Context,
    show_secrets: bool = typer.Option(
        False,
        "--show-secrets",
        help="Whether to show secret values in output",
    ),
):
    """Shows current configuration and exits."""
    ctx = get_ctx(typer_ctx)
    ctx.io.print(do_print_config(ctx, show_secrets))


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
def set_persona(
    typer_ctx: typer.Context,
    persona: str = typer.Argument(..., help="Persona text to set"),
):
    """Set a custom persona for the assistant."""
    ctx = get_ctx(typer_ctx)
    with ctx.dbsession():
        if get_user_id_if_exists(ctx.db, ctx.user_token):
            logging.info(f"No user found for token {ctx.user_token}, creating one")
        do_set_persona(ctx, persona)
        raise typer.Exit()


@app.command(name="reset-persona")
def reset_persona(typer_ctx: typer.Context):
    """Removes any custom persona, reverting to the default."""
    ctx = get_ctx(typer_ctx)
    with ctx.dbsession():
        if not get_user_id_if_exists(ctx.db, ctx.user_token):
            logging.warning(f"No user found for token {ctx.user_token}, so no persona to clear")
            return typer.Exit()
        else:
            reset_system_persona(ctx)
        raise typer.Exit()


@app.command(name="show-persona")
def show_persona(typer_ctx: typer.Context):
    """Print the system persona and exit."""
    ctx = get_ctx(typer_ctx)
    with ctx.dbsession():
        print(get_persona(ctx))
        raise typer.Exit()


@app.command(name="consolidate")
def consolidate(typer_ctx: typer.Context):
    """Consolidate memories and exit."""
    ctx = get_ctx(typer_ctx)
    with ctx.dbsession():
        consolidate_memories(ctx)
        raise typer.Exit()


if __name__ == "__main__":
    app()
