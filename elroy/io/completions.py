"""Helpers for building slash-command autocomplete suggestions and memory panel titles."""

from ..core.ctx import ElroyContext


def get_memory_panel_entries(ctx: ElroyContext) -> list[tuple[str, str]]:
    """Return (display_name, type_key) pairs for the in-context memories sidebar.

    type_key is the raw "{MemoryType}: {name}" string used to look up the source.
    """
    from ..repository.context_messages.queries import get_context_messages
    from ..repository.memories.queries import get_in_context_memories_metadata

    raw = get_in_context_memories_metadata(get_context_messages(ctx))
    return [(t.split(": ", 1)[-1], t) for t in raw]


def get_memory_panel_titles(ctx: ElroyContext) -> list[str]:
    """Return display titles for the in-context memories sidebar."""
    return [display for display, _ in get_memory_panel_entries(ctx)]


def build_completions(ctx: ElroyContext) -> list[str]:
    """Build the full slash-command suggestion list from current memories, reminders, and tools."""
    from itertools import product

    from toolz import concatv, pipe
    from toolz.curried import map as tmap

    from ..core.constants import EXIT
    from ..repository.agenda.tools import get_today_agenda_titles
    from ..repository.context_messages.queries import get_context_messages
    from ..repository.memories.queries import get_active_memories
    from ..repository.recall.queries import is_in_context
    from ..repository.reminders.queries import get_active_reminders
    from ..tools.tools_and_commands import (
        ALL_ACTIVE_AGENDA_COMMANDS,
        ALL_ACTIVE_MEMORY_COMMANDS,
        ALL_ACTIVE_REMINDER_COMMANDS,
        IN_CONTEXT_MEMORY_COMMANDS,
        NON_ARG_PREFILL_COMMANDS,
        NON_CONTEXT_MEMORY_COMMANDS,
        USER_ONLY_COMMANDS,
    )

    context_messages = list(get_context_messages(ctx))
    memories = get_active_memories(ctx)
    reminders = get_active_reminders(ctx)
    agenda_titles = get_today_agenda_titles()

    in_context_memories = sorted([m.get_name() for m in memories if is_in_context(context_messages, m)])
    non_context_memories = sorted([m.get_name() for m in memories if m.get_name() not in in_context_memories])
    reminder_names = sorted([r.get_name() for r in reminders])

    return pipe(
        concatv(
            product(IN_CONTEXT_MEMORY_COMMANDS, in_context_memories),
            product(NON_CONTEXT_MEMORY_COMMANDS, non_context_memories),
            product(ALL_ACTIVE_MEMORY_COMMANDS, [m.get_name() for m in memories]),
            product(ALL_ACTIVE_REMINDER_COMMANDS, reminder_names),
            product(ALL_ACTIVE_AGENDA_COMMANDS, agenda_titles),
        ),
        tmap(lambda x: f"/{x[0].__name__} {x[1]}"),
        list,
        lambda x: x + [f"/{getattr(f, '__name__', f.__class__.__name__)}" for f in NON_ARG_PREFILL_COMMANDS | USER_ONLY_COMMANDS],
        ["/" + EXIT, "/help"].__add__,
    )
