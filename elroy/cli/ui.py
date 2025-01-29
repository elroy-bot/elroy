from functools import partial

from toolz import pipe

from ..config.ctx import ElroyContext


def print_memory_panel(ctx: ElroyContext) -> None:
    """
    Fetches memory for printing in UI

    Passed in messages are easy to make stale, so we fetch within this function!

    """
    from ..io.cli import CliIO
    from ..repository.context_messages.queries import get_context_messages
    from ..repository.memories.queries import get_in_context_memories

    io = ctx.io
    assert isinstance(io, CliIO)
    pipe(
        get_context_messages(ctx),
        partial(get_in_context_memories, ctx),
        io.print_memory_panel,
    )
