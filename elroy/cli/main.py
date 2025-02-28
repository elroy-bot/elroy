import json
import logging
import sys
from bdb import BdbQuit
from datetime import datetime
from functools import partial
from typing import List, Optional

import typer
from rich.table import Table
from toolz import dissoc, pipe

from ..config.constants import MODEL_SELECTION_CONFIG_PANEL
from ..config.ctx import ElroyContext
from ..config.initializer import init_elroy_session
from ..config.logging import setup_logging
from ..config.paths import get_default_config_path, get_default_sqlite_url
from ..io.base import ElroyIO, PlainIO
from ..io.cli import CliIO
from ..io.formatters.rich_formatter import RichFormatter
from ..repository.documents.operations import do_ingest_doc
from ..repository.memories.operations import manually_record_user_memory
from ..repository.user.operations import reset_system_persona
from ..repository.user.operations import set_persona as do_set_persona
from ..repository.user.queries import get_persona, get_user_id_if_exists
from ..tools.developer import do_print_config
from ..utils.utils import datetime_to_string
from .bug_report import create_bug_report_from_exception_if_confirmed
from .chat import handle_chat, handle_message_interactive, handle_message_stdio
from .options import ElroyOption, get_resolved_params, resolve_model_alias
from .updater import check_latest_version, check_updates

MODEL_ALIASES = ["sonnet", "opus", "gpt4o", "gpt4o_mini", "o1", "o1_mini"]

CLI_ONLY_PARAMS = {"disable_assistant_greeting"}


app = typer.Typer(
    help="Elroy CLI",
    context_settings={
        "obj": None,
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
        help="YAML config file path. Values override defaults but are overridden by CLI flags and environment variables.",
        rich_help_panel="Basic Configuration",
    ),
    default_assistant_name: str = ElroyOption(
        "default_assistant_name",
        help="Default name for the assistant.",
        rich_help_panel="Basic Configuration",
    ),
    debug: bool = ElroyOption(
        "debug",
        help="Enable fail-fast error handling and verbose logging output.",
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
    chat_model: str = ElroyOption(
        "chat_model",
        help="The model to use for chat completions.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    chat_model_api_base: Optional[str] = ElroyOption(
        "chat_model_api_base",
        help="Base URL for OpenAI compatible chat model API. Litellm will recognize vars too",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    chat_model_api_key: Optional[str] = ElroyOption(
        "chat_model_api_key",
        help="API key for OpenAI compatible chat model API.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
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
    embedding_model_api_base: Optional[str] = ElroyOption(
        "embedding_model_api_base",
        help="Base URL for OpenAI compatible embedding model API.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    embedding_model_api_key: Optional[str] = ElroyOption(
        "embedding_model_api_key",
        help="API key for OpenAI compatible embedding model API.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    # Model Configuration
    inline_tool_calls: bool = ElroyOption(
        "inline_tool_calls",
        help="Whether to enable inline tool calls in the assistant (better for some open source models)",
        rich_help_panel="Basic Configuration",
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
    max_tokens: int = ElroyOption(
        "max_tokens",
        help="Number of tokens that triggers a context refresh and compresion of messages in the context window.",
        rich_help_panel="Context Management",
    ),
    max_context_age_minutes: float = ElroyOption(
        "max_context_age_minutes",
        help="Maximum age in minutes to keep. Messages older tha this will be dropped from context, regardless of token limits",
        rich_help_panel="Context Management",
    ),
    min_convo_age_for_greeting_minutes: Optional[float] = ElroyOption(
        "min_convo_age_for_greeting_minutes",
        help="Minimum age in minutes of conversation before the assistant will offer a greeting on login. 0 means assistant will offer greeting each time. To disable greeting, set --first=True (This will override any value for min_convo_age_for_greeting_minutes)",
        rich_help_panel="Context Management",
    ),
    disable_assistant_greeting: bool = typer.Option(  # noqa F841
        False,
        "--first",
        "--no-enable-assistant-greeting",
        help="If true, assistant will not send the first message",
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
        hidden=True,
    ),
    user_input_color: str = ElroyOption(
        "user_input_color",
        help="Color for user input.",
        rich_help_panel="UI Configuration",
        hidden=True,
    ),
    assistant_color: str = ElroyOption(
        "assistant_color",
        help="Color for assistant output.",
        rich_help_panel="UI Configuration",
        hidden=True,
    ),
    warning_color: str = ElroyOption(
        "warning_color",
        help="Color for warning messages.",
        rich_help_panel="UI Configuration",
        hidden=True,
    ),
    internal_thought_color: str = ElroyOption(
        "internal_thought_color",
        help="Color for internal thought messages.",
        rich_help_panel="UI Configuration",
        hidden=True,
    ),
    sonnet: bool = typer.Option(  # noqa F841
        False,
        "--sonnet",
        help="Use Anthropic's Sonnet model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    opus: bool = typer.Option(  # noqa F841
        False,
        "--opus",
        help="Use Anthropic's Opus model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    gpt4o: bool = typer.Option(  # noqa F841
        False,
        "--4o",
        help="Use OpenAI's GPT-4o model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    gpt4o_mini: bool = typer.Option(  # noqa F841
        False,
        "--4o-mini",
        help="Use OpenAI's GPT-4o-mini model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    o1: bool = typer.Option(  # noqa F841
        False,
        "--o1",
        help="Use OpenAI's o1 model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    o1_mini: bool = typer.Option(  # noqa F841
        False,
        "--o1-mini",
        help="Use OpenAI's o1-mini model",
        show_default=False,
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
    ),
    openai_api_key: Optional[str] = ElroyOption(
        "openai_api_key",
        help="OpenAI API key, required for OpenAI (or OpenAI compatible) models.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
        hidden=True,
    ),
    openai_api_base: Optional[str] = ElroyOption(
        "openai_api_base",
        help="OpenAI API (or OpenAI compatible) base URL.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
        hidden=True,
    ),
    # Deprecated params
    initial_context_refresh_wait_seconds: int = ElroyOption(  # noqa F841 remove in 0.1.0
        "initial_context_refresh_wait_seconds",
        help="Deprecated, will be removed in future releases",
        rich_help_panel="Memory Consolidation",
        deprecated=True,
    ),
    openai_organization: Optional[str] = ElroyOption(  # noqa F841
        "openai_organization",
        help="OpenAI (or OpenAI compatible) organization ID.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
        deprecated=True,
    ),
    anthropic_api_key: Optional[str] = ElroyOption(  # noqa F841
        "anthropic_api_key",
        help="Anthropic API key, required for Anthropic models.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
        deprecated=True,
    ),
    openai_embedding_api_base: Optional[str] = ElroyOption(  # noqa F841
        "openai_embedding_api_base",
        help="OpenAI API (or OpenAI compatible) base URL for embeddings.",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
        deprecated=True,
    ),
    context_refresh_trigger_tokens: int = ElroyOption(  # noqa F841
        "context_refresh_trigger_tokens",
        help="Number of tokens that triggers a context refresh and compresion of messages in the context window.",
        rich_help_panel="Context Management",
        deprecated=True,
    ),
    context_refresh_target_tokens: int = ElroyOption(
        "context_refresh_target_tokens",
        help="Target number of tokens after context refresh / context compression, how many tokens to aim to keep in context.",
        rich_help_panel="Context Management",
        deprecated=True,
    ),
):
    """Common parameters."""

    setup_logging()

    if typer_ctx.invoked_subcommand is None:
        chat(typer_ctx)


@app.command(name="chat")
def chat(typer_ctx: typer.Context):
    """Opens an interactive chat session. (default command)"""

    # extra check needed since chat is the default command
    if not typer_ctx.params and typer_ctx.parent:
        params = typer_ctx.parent.params
    else:
        params = typer_ctx.params

    io = get_io(**params)

    if sys.stdin.isatty():
        ctx = get_ctx(use_background_threads=True, **params)
        assert isinstance(io, CliIO)

        check_updates(io)

        with init_elroy_session(ctx, io, True, True):
            try:
                handle_chat(io, params["disable_assistant_greeting"], ctx)
            except BdbQuit:
                logging.info("Exiting...")
            except EOFError:
                logging.info("Exiting...")
            except Exception as e:
                if "Unsupported param: tools" in str(e):
                    raise typer.BadParameter(
                        f"Tool use not supported by model {ctx.chat_model.name}. Try starting with --inline-tool-calls"
                    )
                else:
                    create_bug_report_from_exception_if_confirmed(io, ctx, e)
    else:
        ctx = get_ctx(use_background_threads=False, **params)
        message = sys.stdin.read()
        assert isinstance(io, PlainIO)
        with init_elroy_session(ctx, io, True, False):
            handle_message_stdio(ctx, io, message, None)


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
    assert typer_ctx.parent
    ctx = get_ctx(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    with init_elroy_session(ctx, io, True, False):
        if sys.stdin.isatty() and not message:
            assert isinstance(io, CliIO)
            handle_message_interactive(ctx, io, tool)
        else:
            assert message
            handle_message_stdio(ctx, io, message, tool)


@app.command(name="print-tool-schemas")
def print_tools(
    typer_ctx: typer.Context,
    tool: Optional[str] = typer.Argument(None, help="Tool to print schema for"),
):
    """Prints the schema for a tool and exits."""
    assert typer_ctx.parent
    ctx = get_ctx(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    io.print(ctx.tool_registry.get_schemas())  # type: ignore


@app.command(name="remember")
def cli_remember(
    typer_ctx: typer.Context,
    text: Optional[str] = typer.Argument(
        None,
        help="Text to remember. If not provided, will prompt interactively",
    ),
):
    """Create a new memory from text or interactively."""
    assert typer_ctx.parent
    ctx = get_ctx(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    with init_elroy_session(ctx, io, True, False):
        if text:
            memory_name = f"Memory from CLI, created {datetime_to_string(datetime.now())}"
            manually_record_user_memory(ctx, text, memory_name)
            io.info(f"Memory created: {memory_name}")
            raise typer.Exit()

        elif sys.stdin.isatty():
            assert isinstance(io, CliIO)
            memory_text = io.prompt_user(ctx.thread_pool, 0, "Enter the memory text:")
            memory_text += f"\nManually entered memory, at: {datetime_to_string(datetime.now())}"
            # Optionally get memory name
            memory_name = io.prompt_user(ctx.thread_pool, 0, "Enter memory name (optional, press enter to skip):")
            try:
                manually_record_user_memory(ctx, memory_text, memory_name)
                io.info(f"Memory created: {memory_name}")
                raise typer.Exit()
            except ValueError as e:
                io.warning(f"Error creating memory: {e}")
                raise typer.Exit(1)
            except EOFError:
                io.info("Cancelled.")
                raise typer.Exit()
        else:
            memory_text = sys.stdin.read()
            metadata = "Memory ingested from stdin\n" f"Ingested at: {datetime_to_string(datetime.now())}\n"
            memory_text = f"{metadata}\n{memory_text}"
            memory_name = f"Memory from stdin, ingested {datetime_to_string(datetime.now())}"
            manually_record_user_memory(ctx, memory_text, memory_name)
            io.info(f"Memory created: {memory_name}")
            raise typer.Exit()


@app.command(name="list-models")
def list_models():
    """Lists supported chat models and exits."""
    from ..config.models_aliases import (
        get_supported_anthropic_models,
        get_supported_openai_models,
    )

    for m in get_supported_openai_models():
        print(f"{m} (OpenAI)")
    for m in get_supported_anthropic_models():
        print(f"{m} (Anthropic)")
    raise typer.Exit()


@app.command(name="list-tools")
def list_tools(
    typer_ctx: typer.Context,
):
    assert typer_ctx.parent
    ctx = get_ctx(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    tools = ctx.tool_registry.get_schemas()

    table = Table(title="Available Tools")
    table.add_column("Tool", style="bold")
    table.add_column("Description")

    for tool in tools:
        ctx.tool_registry.get(tool["function"]["name"])

        table.add_row(
            tool["function"]["name"],
            tool["function"]["description"].split("\n")[0],
        )
    io.console.print(table)


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
    assert typer_ctx.parent
    ctx = get_ctx(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    io.print(do_print_config(ctx, show_secrets))


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
def cli_set_persona(
    typer_ctx: typer.Context,
    persona: str = typer.Argument(..., help="Persona text to set"),
):
    """Set a custom persona for the assistant."""
    assert typer_ctx.parent
    ctx = get_ctx(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    with init_elroy_session(ctx, io, True, False):
        if get_user_id_if_exists(ctx.db, ctx.user_token):
            logging.info(f"No user found for token {ctx.user_token}, creating one")
        do_set_persona(ctx, persona)
        raise typer.Exit()


@app.command(name="reset-persona")
def reset_persona(typer_ctx: typer.Context):
    """Removes any custom persona, reverting to the default."""
    assert typer_ctx.parent
    ctx = get_ctx(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    with init_elroy_session(ctx, io, True, False):
        if not get_user_id_if_exists(ctx.db, ctx.user_token):
            logging.warning(f"No user found for token {ctx.user_token}, so no persona to clear")
            return typer.Exit()
        else:
            reset_system_persona(ctx)
        raise typer.Exit()


@app.command(name="show-persona")
def show_persona(typer_ctx: typer.Context):
    """Print the system persona and exit."""
    assert typer_ctx.parent
    ctx = get_ctx(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    with init_elroy_session(ctx, io, True, False):
        print(get_persona(ctx))
        raise typer.Exit()


@app.command(name="ingest")
def ingest_doc(
    typer_ctx: typer.Context,
    path: str = typer.Argument(..., help="Path to document to ingest"),
    force_refresh: bool = typer.Option(
        False,
        "--force-refresh",
        "-f",
        help="If true, any existing ingested document at the given path will be discarded, and the document will be re-ingested.",
    ),
):
    """Ingests document at the given path into memory."""

    assert typer_ctx.parent
    ctx = get_ctx(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    with init_elroy_session(ctx, io, True, False):
        do_ingest_doc(ctx, path, force_refresh)


mcp_app = typer.Typer(help="MCP server commands")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command(name="print-config")
def mcp_print_config(
    typer_ctx: typer.Context,
    local: bool = typer.Option(
        False,
        "--local",
        help="Print config using the same instance of Elroy running this command",
    ),
):
    """Print MCP server configuration to stdout"""
    from ..mcp.config import get_mcp_config, is_uv_installed

    assert typer_ctx.parent and typer_ctx.parent.parent
    ctx = get_ctx(use_background_threads=False, **typer_ctx.parent.parent.params)
    io = get_io(**typer_ctx.parent.parent.params)

    if not is_uv_installed():
        io.warning("uv not detected. uv is required to run Elroy MCP server")

    pipe(
        ctx,
        partial(get_mcp_config, local),
        lambda d: json.dumps(d, indent=2),
        print,
    )


def get_ctx(use_background_threads: bool, **kwargs) -> ElroyContext:
    for m in MODEL_ALIASES:
        if kwargs.get(m):
            logging.info(f"Model alias {m} selected")
            resolved = resolve_model_alias(m)
            if not resolved:
                logging.warning("Model alias not found")
            else:
                kwargs["chat_model"] = resolved
        del kwargs[m]

    params = pipe(
        kwargs,
        lambda x: dissoc(x, *CLI_ONLY_PARAMS),
        lambda x: get_resolved_params(**x),
    )

    return ElroyContext.init(use_background_threads=use_background_threads, **params)


def get_io(**kwargs) -> ElroyIO:
    params = get_resolved_params(**kwargs)

    if sys.stdin.isatty():
        return CliIO(
            RichFormatter(
                system_message_color=params["system_message_color"],
                assistant_message_color=params["assistant_color"],
                user_input_color=params["user_input_color"],
                warning_color=params["warning_color"],
                internal_thought_color=params["internal_thought_color"],
            ),
            show_internal_thought=params["show_internal_thought"],
        )
    else:
        return PlainIO()


if __name__ == "__main__":
    app()
