from functools import partial

from rich.text import Text
from toolz import pipe

from ..config.ctx import ElroyContext
from ..io.cli import CliIO


def print_memory_panel(io: CliIO, ctx: ElroyContext) -> None:
    """
    Fetches memory for printing in UI

    Passed in messages are easy to make stale, so we fetch within this function!

    """
    from ..repository.context_messages.queries import get_context_messages
    from ..repository.memories.queries import get_in_context_memories

    pipe(
        get_context_messages(ctx),
        partial(get_in_context_memories, ctx),
        io.print_memory_panel,
    )


def print_title_ruler(io: CliIO, assistant_name: str):
    io.console.rule(
        Text(assistant_name, justify="center", style=io.user_input_color),
        style=io.user_input_color,
    )
