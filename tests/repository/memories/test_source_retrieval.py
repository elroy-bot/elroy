from tests.utils import process_test_message

from elroy.config.ctx import ElroyContext
from elroy.repository.goals.tools import create_goal, mark_goal_completed
from elroy.repository.memories.consolidation import consolidate_memories
from elroy.repository.memories.queries import get_active_memories
from elroy.repository.memories.tools import (
    create_memory,
    get_source_content,
    get_source_list_for_memory,
)


def test_goal_source(ctx: ElroyContext):
    create_goal(ctx, "Run a marathon")
    mark_goal_completed(ctx, "Run a marathon")
    memory = get_active_memories(ctx)[-1]

    source_list = get_source_list_for_memory(ctx, memory.name)
    assert source_list == "Goal: Run a marathon", "Source list not as expected"

    source_content = get_source_content(ctx, "Goal", "Run a marathon")
    assert "Goal: Run a marathon" in source_content, "Source content not as expected"


def test_memory_source(ctx: ElroyContext):
    ctx.memory_cluster_similarity_threshold = 0.99

    create_memory(ctx, "Running progress", "I ran a marathon today")
    create_memory(ctx, "Running progress", "I did some running today")
    create_memory(ctx, "Run today", "I ran 24 miles today")
    create_memory(ctx, "Run today", "I ran a total of 24 miles today")

    consolidate_memories(ctx)

    memory = get_active_memories(ctx)[-1]
    source_list = get_source_list_for_memory(ctx, memory.name)
    assert "Memory: Running progress" in source_list

    assert "Running progress" in get_source_content(ctx, "Memory", "Running progress")


def test_context_message_source(ctx: ElroyContext):
    process_test_message(ctx, "Hello, I ran a marathon today!")
    create_memory(ctx, "Running progress", "I ran a marathon today")
    source_list = get_source_list_for_memory(ctx, "Running progress")
    assert "ContextMessageSet" in source_list

    name = source_list.split(" ")[-1]
    assert "Hello, I ran a marathon today" in get_source_content(ctx, "ContextMessageSet", name)
