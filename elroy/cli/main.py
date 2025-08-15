import json
import sys
from bdb import BdbQuit
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional

import typer
from rich.table import Table
from sqlmodel import col
from toolz import pipe

from elroy.cli.options import get_str_from_stdin_or_arg

from .. import __version__
from ..config.paths import get_default_config_path, get_default_sqlite_url
from ..core.constants import KNOWN_MODELS, MODEL_SELECTION_CONFIG_PANEL
from ..core.ctx import ElroyContext
from ..core.logging import get_logger, setup_core_logging, setup_file_logging
from ..core.session import init_elroy_session
from ..db.db_models import Reminder
from ..io.base import ElroyIO, PlainIO
from ..io.cli import CliIO
from ..io.formatters.rich_formatter import RichFormatter
from ..repository.documents.operations import do_ingest, do_ingest_dir
from ..repository.memories.operations import manually_record_user_memory
from ..repository.user.operations import reset_system_persona
from ..repository.user.operations import set_persona as do_set_persona
from ..repository.user.queries import get_persona, get_user_id_if_exists
from ..tools.developer import do_print_config
from ..utils.clock import utc_now
from ..utils.utils import datetime_to_string
from .bug_report import create_bug_report_from_exception_if_confirmed
from .chat import handle_chat, handle_message_stdio
from .options import ElroyOption, get_resolved_params
from .updater import check_latest_version, check_updates

MODEL_ALIASES = ["sonnet", "opus", "gpt4o", "gpt4o_mini", "o1", "o1_mini"]

CLI_ONLY_PARAMS = {"enable_assistant_greeting", "show_memory_panel"}


setup_core_logging()
setup_file_logging()

logger = get_logger()

app = typer.Typer(
    help=f"Elroy {__version__}",
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
        hidden=True,
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
    include_base_tools: bool = ElroyOption(
        "include_base_tools",
        help="Whether to load base tools from the Elroy package",
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
        hidden=True,
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
        hidden=True,
    ),
    min_convo_age_for_greeting_minutes: Optional[float] = ElroyOption(
        "min_convo_age_for_greeting_minutes",
        help="Minimum age in minutes of conversation before the assistant will offer a greeting on login. 0 means assistant will offer greeting each time. To disable greeting, set --first=True (This will override any value for min_convo_age_for_greeting_minutes)",
        rich_help_panel="Context Management",
        hidden=True,
    ),
    enable_assistant_greeting: bool = typer.Option(  # noqa F841
        False,
        "--greeting",
        help="If true, assistant will send the first message",
        rich_help_panel="Context Management",
    ),
    # Memory Consolidation
    memories_between_consolidation: int = ElroyOption(
        "memories_between_consolidation",
        help="How many memories to create before triggering a memory consolidation operation.",
        rich_help_panel="Memory Consolidation",
        hidden=True,
    ),
    # Memory Consolidation
    messages_between_memory: int = ElroyOption(
        "messages_between_memory",
        help="Max number of messages that can be processed before memory creation is triggered",
        rich_help_panel="Memory Consolidation",
        hidden=True,
    ),
    l2_memory_relevance_distance_threshold: float = ElroyOption(
        "l2_memory_relevance_distance_threshold",
        help="L2 distance threshold for memory relevance.",
        rich_help_panel="Memory Consolidation",
        hidden=True,
    ),
    memory_cluster_similarity_threshold: float = ElroyOption(
        "memory_cluster_similarity_threshold",
        help="Threshold for memory cluster similarity.",
        rich_help_panel="Memory Consolidation",
        hidden=True,
    ),
    max_memory_cluster_size: int = ElroyOption(
        "max_memory_cluster_size",
        help="The maximum number of memories that can be consolidated into a single memory at once.",
        rich_help_panel="Memory Consolidation",
        hidden=True,
    ),
    min_memory_cluster_size: int = ElroyOption(
        "min_memory_cluster_size",
        help="The minimum number of memories that can be consolidated into a single memory at once.",
        rich_help_panel="Memory Consolidation",
        hidden=True,
    ),
    # UI Configuration
    show_memory_panel: bool = ElroyOption(  # noqa F841
        "show_memory_panel",
        help="Whether to display the memory panel in the UI.",
        rich_help_panel="UI Configuration",
    ),
    show_internal_thought: bool = ElroyOption(
        "show_internal_thought",
        help="Show the assistant's internal thought monologue like memory consolidation and internal reflection.",
        rich_help_panel="Basic Configuration",
    ),
    reflect: bool = ElroyOption(
        "reflect",
        help="If true, the assistant will reflect on memories it recalls. This will lead to slower but richer responses. If false, memories will be less processed when recalled into memory.",
        rich_help_panel="Basic Configuration",
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
    shell_commands: bool = ElroyOption(
        "shell_commands",
        help="Whether to enable shell commands.",
        rich_help_panel="Basic Configuration",
        hidden=True,
    ),
    allowed_shell_command_prefixes: List[str] = ElroyOption(
        "allowed_shell_command_prefixes",
        help="Allowed prefixes for shell commands.",
        rich_help_panel="Basic Configuration",
        hidden=True,
    ),
):
    """Common parameters."""

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
        ctx = ElroyContext.init(use_background_threads=True, **params)
        assert isinstance(io, CliIO)

        check_updates(io)

        # Initialize the APScheduler
        from ..core.async_tasks import init_scheduler, shutdown_scheduler

        init_scheduler()

        with init_elroy_session(ctx, io, True, True):
            try:
                handle_chat(io, params["enable_assistant_greeting"], ctx)
            except BdbQuit:
                logger.info("Exiting...")
            except EOFError:
                logger.info("Exiting...")
            except Exception as e:
                if "Unsupported param: tools" in str(e):
                    raise typer.BadParameter(
                        f"Tool use not supported by model {ctx.chat_model.name}. Try starting with --inline-tool-calls"
                    )
                else:
                    create_bug_report_from_exception_if_confirmed(io, ctx, e)
            finally:
                shutdown_scheduler(wait=False)

    else:
        ctx = ElroyContext.init(use_background_threads=False, **params)
        message = sys.stdin.read()
        assert isinstance(io, PlainIO)
        with init_elroy_session(ctx, io, True, False):
            handle_message_stdio(ctx, io, message, None)


@app.command(name="message")
def message(
    typer_ctx: typer.Context,
    message: str = typer.Argument(
        None,
        callback=get_str_from_stdin_or_arg,
        help="The message to process.",
    ),
    tool: str = typer.Option(
        None,
        "--tool",
        "-t",
        help="Specifies the tool to use in responding to a message",
    ),
    plain: bool = typer.Option(
        False,
        "--plain",
        help="Use plain text output instead of rich text.",
    ),
):
    """Process a single message and exit."""
    assert typer_ctx.parent
    ctx = ElroyContext.init(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(plain=plain, **typer_ctx.parent.params)
    with init_elroy_session(ctx, io, True, False):
        handle_message_stdio(ctx, io, message, tool)


@app.command(name="print-tool-schemas")
def print_tools(
    typer_ctx: typer.Context,
    tool: Optional[str] = typer.Argument(None, help="Tool to print schema for"),
):
    """Prints the schema for a tool and exits."""
    assert typer_ctx.parent
    ctx = ElroyContext.init(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    io.print(ctx.tool_registry.get_schemas())  # type: ignore


@app.command(name="remember")
def cli_remember(
    typer_ctx: typer.Context,
    text: str = typer.Argument(
        None,
        callback=get_str_from_stdin_or_arg,
        help="Text to remember. If not provided, will read from stdin or prompt interactively",
    ),
):
    """Create a new memory from text or interactively."""
    assert typer_ctx.parent
    ctx = ElroyContext.init(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    with init_elroy_session(ctx, io, True, False):
        memory_name = f"Memory from CLI, created {datetime_to_string(utc_now())}"
        manually_record_user_memory(ctx, text, memory_name)
        io.info(f"Memory created: {memory_name}")
        raise typer.Exit()


@app.command(name="list-models")
def list_models():
    """Lists supported chat models and exits."""

    for provider, models in KNOWN_MODELS.items():
        print(f"{provider.value} models:")
        for m in models:
            print(f"    {m}")

    raise typer.Exit()


@app.command(name="list-tools")
def list_tools(
    typer_ctx: typer.Context,
):
    assert typer_ctx.parent
    ctx = ElroyContext.init(use_background_threads=False, **typer_ctx.parent.params)
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


@app.command(name="stats")
def user_stats(
    typer_ctx: typer.Context,
):
    """Show user statistics."""
    assert typer_ctx.parent
    ctx = ElroyContext.init(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)

    with init_elroy_session(ctx, io, True, False):
        from sqlmodel import func, select

        from ..db.db_models import DocumentExcerpt, Memory, Message, VectorStorage

        # Get counts for all data types
        total_messages = ctx.db.exec(select(func.count(col(Message.id))).where(Message.user_id == ctx.user_id)).first() or 0

        total_memories = ctx.db.exec(select(func.count(col(Memory.id))).where(Memory.user_id == ctx.user_id)).first() or 0

        active_memories = (
            ctx.db.exec(select(func.count(col(Memory.id))).where(Memory.user_id == ctx.user_id, Memory.is_active == True)).first() or 0
        )

        total_document_excerpts = (
            ctx.db.exec(select(func.count(col(DocumentExcerpt.id))).where(DocumentExcerpt.user_id == ctx.user_id)).first() or 0
        )

        active_document_excerpts = (
            ctx.db.exec(
                select(func.count(col(DocumentExcerpt.id))).where(DocumentExcerpt.user_id == ctx.user_id, DocumentExcerpt.is_active == True)
            ).first()
            or 0
        )

        total_reminders = ctx.db.exec(select(func.count(col(Reminder.id))).where(Reminder.user_id == ctx.user_id)).first() or 0

        active_reminders = (
            ctx.db.exec(select(func.count(col(Reminder.id))).where(Reminder.user_id == ctx.user_id, Reminder.is_active == True)).first()
            or 0
        )

        # Count vectors for this user's entities
        vectors_for_memories = (
            ctx.db.exec(
                select(func.count(col(VectorStorage.id))).where(
                    VectorStorage.source_type == Memory.__class__.__name__,
                    col(VectorStorage.source_id).in_(select(col(Memory.id)).where(Memory.user_id == ctx.user_id)),
                )
            ).first()
            or 0
        )

        vectors_for_documents = (
            ctx.db.exec(
                select(func.count(col(VectorStorage.id))).where(
                    VectorStorage.source_type == DocumentExcerpt.__class__.__name__,
                    col(VectorStorage.source_id).in_(select(col(DocumentExcerpt.id)).where(DocumentExcerpt.user_id == ctx.user_id)),
                )
            ).first()
            or 0
        )

        vectors_for_reminders = (
            ctx.db.exec(
                select(func.count(col(VectorStorage.id))).where(
                    VectorStorage.source_type == Reminder.__class__.__name__,
                    col(VectorStorage.source_id).in_(select(col(Reminder.id)).where(Reminder.user_id == ctx.user_id)),
                )
            ).first()
            or 0
        )

        total_vectors = vectors_for_memories + vectors_for_documents + vectors_for_reminders

        # Create and display the table
        table = Table(title=f"User Statistics (Token: {ctx.user_token})")
        table.add_column("Metric", style="bold")
        table.add_column("Count", justify="right", style="cyan")

        table.add_row("Total Messages", str(total_messages))
        table.add_row("Total Memories", str(total_memories))
        table.add_row("Active Memories", str(active_memories))
        table.add_row("Total Document Excerpts", str(total_document_excerpts))
        table.add_row("Active Document Excerpts", str(active_document_excerpts))
        table.add_row("Total Reminders", str(total_reminders))
        table.add_row("Active Reminders", str(active_reminders))
        table.add_row("Total Vectors Stored", str(total_vectors))

        io.console.print(table)
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
    assert typer_ctx.parent
    ctx = ElroyContext.init(use_background_threads=False, **typer_ctx.parent.params)
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
    ctx = ElroyContext.init(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    with init_elroy_session(ctx, io, True, False):
        if get_user_id_if_exists(ctx.db, ctx.user_token):
            logger.info(f"No user found for token {ctx.user_token}, creating one")
        do_set_persona(ctx, persona)
        raise typer.Exit()


@app.command(name="reset-persona")
def reset_persona(typer_ctx: typer.Context):
    """Removes any custom persona, reverting to the default."""
    assert typer_ctx.parent
    ctx = ElroyContext.init(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    with init_elroy_session(ctx, io, True, False):
        if not get_user_id_if_exists(ctx.db, ctx.user_token):
            logger.warning(f"No user found for token {ctx.user_token}, so no persona to clear")
            return typer.Exit()
        else:
            reset_system_persona(ctx)
        raise typer.Exit()


@app.command(name="show-persona")
def show_persona(typer_ctx: typer.Context):
    """Print the system persona and exit."""
    assert typer_ctx.parent
    ctx = ElroyContext.init(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)
    with init_elroy_session(ctx, io, True, False):
        print(get_persona(ctx))
        raise typer.Exit()


# Future improvements: better duplicate detection:
# - docs that have the same content
# - if the location is different, take the one with the more recent timestamp
# - need a mark_source_doc_inactive function


@app.command(name="ingest")
def ingest_doc(
    typer_ctx: typer.Context,
    path: Path = typer.Argument(
        ...,
        help="Path to document or directory to ingest",
        exists=True,
        file_okay=True,
        dir_okay=True,
        resolve_path=True,
    ),
    force_refresh: bool = typer.Option(
        False,
        "--force-refresh",
        "-f",
        help="If true, any existing ingested documents will be discarded and re-ingested.",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="If path is a directory, recursively ingest all documents within it.",
    ),
    include: List[str] = typer.Option(
        [],
        "--include",
        "-i",
        help="Glob pattern for files to include (e.g. '*.txt,*.md'). Multiple patterns can be comma-separated.",
    ),
    exclude: List[str] = typer.Option(
        [],
        "--exclude",
        "-e",
        help="Glob pattern for files to exclude (e.g. '*.log'). Can also be used to exclude directories.",
    ),
):
    """Ingests document(s) at the given path into memory. Can process single files or directories."""

    assert typer_ctx.parent
    ctx = ElroyContext.init(use_background_threads=False, **typer_ctx.parent.params)
    io = get_io(**typer_ctx.parent.params)

    with init_elroy_session(ctx, io, True, False):
        if path.is_file():
            result = do_ingest(ctx, path, force_refresh)
            io.info(f"Document ingestion result: {result.name}")
        elif path.is_dir():
            from rich.live import Live
            from rich.table import Table

            from elroy.repository.documents.operations import DocIngestStatus

            # Initialize status counts
            # Create a function to generate the status table
            def generate_status_table(statuses: Dict[DocIngestStatus, int]):
                table = Table()
                table.add_column("Status", style="bold")
                table.add_column("Count", justify="right")

                for status, count in statuses.items():
                    table.add_row(status.name, str(count))

                return table

            # Use Rich's Live display to update the table in real-time
            with Live(generate_status_table({s: 0 for s in DocIngestStatus}), refresh_per_second=8) as live:
                # Consume the generator and update the display
                for status_update in do_ingest_dir(ctx, path, force_refresh, recursive, include, exclude):
                    live.update(generate_status_table(status_update))
        else:
            io.warning(f"Path {path} is neither a file nor a directory")


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
    ctx = ElroyContext.init(use_background_threads=False, **typer_ctx.parent.parent.params)
    io = get_io(**typer_ctx.parent.parent.params)

    if not is_uv_installed():
        io.warning("uv not detected. uv is required to run Elroy MCP server")

    pipe(
        ctx,
        partial(get_mcp_config, local),
        lambda d: json.dumps(d, indent=2),
        print,
    )


def get_io(**kwargs) -> ElroyIO:
    params = get_resolved_params(**kwargs)

    if sys.stdin.isatty() and not params.get("plain", False):
        return CliIO(
            RichFormatter(
                system_message_color=params["system_message_color"],
                assistant_message_color=params["assistant_color"],
                user_input_color=params["user_input_color"],
                warning_color=params["warning_color"],
                internal_thought_color=params["internal_thought_color"],
            ),
            show_internal_thought=params["show_internal_thought"],
            show_memory_panel=params["show_memory_panel"],
        )
    else:
        return PlainIO()


if __name__ == "__main__":
    app()
