from rich.text import Text
from toolz import pipe

from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..io.cli import CliIO

logger = get_logger()


def print_memory_panel(io: CliIO, ctx: ElroyContext) -> None:
    """
    Fetches memory for printing in UI

    Passed in messages are easy to make stale, so we fetch within this function!

    """
    from ..repository.context_messages.queries import get_context_messages
    from ..repository.memories.queries import get_in_context_memories_metadata

    if not io.show_memory_panel:
        logger.warning("print_memory_panel called, but Memory panel is disabled")
        return

    pipe(
        get_context_messages(ctx),
        get_in_context_memories_metadata,
        io.print_memory_panel,
    )


def print_live_panel(io: CliIO) -> None:
    """
    Print the live panel showing background operation status if enabled and has active jobs.
    """

    import pdb

    pdb.set_trace()
    if not io.show_live_panel:
        logger.debug("print_live_panel called, but Live panel is disabled")
        return

    if not io.live_panel.has_active_jobs:
        logger.debug("print_live_panel called, but no active jobs")
        return

    # Display the current state of the live panel
    panel = io.live_panel._create_panel()
    io.console.print(panel)


def print_title_ruler(io: CliIO, assistant_name: str):
    io.console.rule(
        Text(assistant_name, justify="center", style=io.user_input_color),
        style=io.user_input_color,
    )


def print_model_selection(io: CliIO, ctx: ElroyContext):
    chat_msg = f"Using chat model: {ctx.chat_model.name}" + (" (inferred from env)" if ctx.is_chat_model_inferred else "")

    io.console.print(Text(chat_msg, style=io.formatter.internal_thought_color), justify="center")
    io.console.print()
