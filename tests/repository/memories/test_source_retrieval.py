from elroy.core.ctx import ElroyConfig
from elroy.core.session import open_turn_context
from elroy.repository.memories.consolidation import create_consolidated_memory
from elroy.repository.memories.factory import build_memory_lifecycle_orchestrator
from elroy.repository.memories.tools import (
    create_memory,
    get_source_content_for_memory,
    get_source_list_for_memory,
)
from tests.utils import process_test_message


def test_memory_source(ctx: ElroyConfig):
    with open_turn_context(ctx) as turn:
        memory_lifecycle_orchestrator = build_memory_lifecycle_orchestrator(turn)
        memory1 = memory_lifecycle_orchestrator.do_create_memory(
            "Running progress",
            "I ran a marathon today",
            [],
            False,
        )
        memory2 = memory_lifecycle_orchestrator.do_create_memory(
            "Run today",
            "I ran 24 miles today",
            [],
            False,
        )

    create_consolidated_memory(
        ctx,
        "Running summary",
        "The user ran a marathon and later reported running 24 miles in total.",
        [memory1, memory2],
    )

    source_list = get_source_list_for_memory(ctx, "Running summary")
    assert ("Memory", "Running progress") in source_list
    assert ("Memory", "Run today") in source_list

    source_index = source_list.index(("Memory", "Running progress"))
    assert "Running progress" in get_source_content_for_memory(ctx, "Running summary", source_index)


def test_context_message_source(ctx: ElroyConfig):
    process_test_message(ctx, "Hello, I ran a marathon today!")
    create_memory(ctx, "Running progress", "I ran a marathon today")
    source_list = get_source_list_for_memory(ctx, "Running progress")
    assert "ContextMessageSet" in source_list[0]

    assert "Hello, I ran a marathon today" in get_source_content_for_memory(ctx, "Running progress", 0)
