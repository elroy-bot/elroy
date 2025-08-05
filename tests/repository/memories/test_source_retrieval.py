from tests.utils import process_test_message

from elroy.core.ctx import ElroyContext
from elroy.repository.memories.consolidation import consolidate_memories
from elroy.repository.memories.queries import get_active_memories
from elroy.repository.memories.tools import (
    create_memory,
    get_source_content_for_memory,
    get_source_list_for_memory,
)


def test_memory_source(ctx: ElroyContext):
    ctx.memory_cluster_similarity_threshold = 0.99

    create_memory(ctx, "Running progress", "I ran a marathon today")
    create_memory(ctx, "Running progress", "I did some running today")
    create_memory(ctx, "Run today", "I ran 24 miles today")
    create_memory(ctx, "Run today", "I ran a total of 24 miles today")

    consolidate_memories(ctx)

    memory = get_active_memories(ctx)[-1]
    source_list = get_source_list_for_memory(ctx, memory.name)
    assert ("Memory", "Running progress") in source_list

    assert "Running progress" in get_source_content_for_memory(ctx, memory.name, 0)


def test_context_message_source(ctx: ElroyContext):
    process_test_message(ctx, "Hello, I ran a marathon today!")
    create_memory(ctx, "Running progress", "I ran a marathon today")
    source_list = get_source_list_for_memory(ctx, "Running progress")
    assert "ContextMessageSet" in source_list[0]

    assert "Hello, I ran a marathon today" in get_source_content_for_memory(ctx, "Running progress", 0)
