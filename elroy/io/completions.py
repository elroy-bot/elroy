"""Helpers for building slash-command autocomplete suggestions and memory panel titles."""

from ..core.ctx import ElroyConfig
from ..core.session import run_with_turn
from ..core.turn import TurnContext
from ..repository.context_messages.factory import build_context_message_read_store
from ..repository.context_messages.session import build_context_message_session
from ..repository.memories.queries import do_get_active_memories, get_in_context_memories_metadata
from ..repository.reminders.queries import do_get_active_due_items


class CompletionsBuilder:
    def __init__(self, turn: TurnContext):
        self.turn = turn

    def get_memory_panel_entries(self) -> list[tuple[str, str]]:
        """Return (display_name, type_key) pairs for the in-context memories sidebar.

        type_key is the raw "{MemoryType}: {name}" string used to look up the source.
        """
        context_message_read_store = build_context_message_read_store(build_context_message_session(self.turn))
        raw = get_in_context_memories_metadata(context_message_read_store.get_context_messages())
        return [(t.split(": ", 1)[-1], t) for t in raw]

    def get_memory_panel_titles(self) -> list[str]:
        """Return display titles for the in-context memories sidebar."""
        return [display for display, _ in self.get_memory_panel_entries()]

    def build_completions(self) -> list[str]:
        """Build the full slash-command suggestion list from current memories, due items, agenda items, and tools."""
        from itertools import product

        from toolz import concatv, pipe
        from toolz.curried import map as tmap

        from ..core.constants import EXIT
        from ..repository.agenda.tools import do_get_active_agenda_titles
        from ..repository.recall.queries import is_in_context
        from ..tools.tools_and_commands import (
            ALL_ACTIVE_AGENDA_COMMANDS,
            ALL_ACTIVE_DUE_ITEM_COMMANDS,
            ALL_ACTIVE_MEMORY_COMMANDS,
            IN_CONTEXT_MEMORY_COMMANDS,
            NON_ARG_PREFILL_COMMANDS,
            NON_CONTEXT_MEMORY_COMMANDS,
            USER_ONLY_COMMANDS,
        )

        context_message_read_store = build_context_message_read_store(build_context_message_session(self.turn))
        context_messages = list(context_message_read_store.get_context_messages())
        memories = do_get_active_memories(self.turn)
        due_items = do_get_active_due_items(self.turn)
        agenda_titles = do_get_active_agenda_titles(self.turn)

        in_context_memories = sorted([m.get_name() for m in memories if is_in_context(context_messages, m)])
        non_context_memories = sorted([m.get_name() for m in memories if m.get_name() not in in_context_memories])
        due_item_names = sorted([r.get_name() for r in due_items])

        return pipe(
            concatv(
                product(IN_CONTEXT_MEMORY_COMMANDS, in_context_memories),
                product(NON_CONTEXT_MEMORY_COMMANDS, non_context_memories),
                product(ALL_ACTIVE_MEMORY_COMMANDS, [m.get_name() for m in memories]),
                product(ALL_ACTIVE_DUE_ITEM_COMMANDS, due_item_names),
                product(ALL_ACTIVE_AGENDA_COMMANDS, agenda_titles),
            ),
            tmap(lambda x: f"/{x[0].__name__} {x[1]}"),
            list,
            lambda x: x + [f"/{getattr(f, '__name__', f.__class__.__name__)}" for f in NON_ARG_PREFILL_COMMANDS | USER_ONLY_COMMANDS],
            ["/" + EXIT, "/help"].__add__,
        )


def do_get_memory_panel_entries(turn: TurnContext) -> list[tuple[str, str]]:
    return CompletionsBuilder(turn).get_memory_panel_entries()


def do_get_memory_panel_titles(turn: TurnContext) -> list[str]:
    return CompletionsBuilder(turn).get_memory_panel_titles()


def do_build_completions(turn: TurnContext) -> list[str]:
    return CompletionsBuilder(turn).build_completions()


def get_memory_panel_entries(ctx: ElroyConfig) -> list[tuple[str, str]]:
    return run_with_turn(ctx, do_get_memory_panel_entries)


def get_memory_panel_titles(ctx: ElroyConfig) -> list[str]:
    return run_with_turn(ctx, do_get_memory_panel_titles)


def build_completions(ctx: ElroyConfig) -> list[str]:
    return run_with_turn(ctx, do_build_completions)
