from typing import List

import pytest
from sqlmodel import select

from elroy.core.constants import ASSISTANT, USER
from elroy.core.ctx import ElroyContext
from elroy.db.db_models import MemoryOperationTracker
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.operations import (
    add_context_message,
    add_context_messages,
)
from elroy.repository.memories.operations import (
    do_create_op_tracked_memory,
    get_or_create_memory_op_tracker,
)
from elroy.repository.memories.queries import get_active_memories


@pytest.fixture(scope="function")
def mem_op_ctx(ctx: ElroyContext):
    ctx.use_background_threads = False
    ctx.messages_between_memory = 3
    return ctx


@pytest.fixture(scope="session")
def dummy_msgs():
    return [
        ContextMessage(role=USER, content="Test message 1", chat_model=None),
        ContextMessage(role=ASSISTANT, content="Test response 1", chat_model=None),
        ContextMessage(role=USER, content="Test message 2", chat_model=None),
        ContextMessage(role=ASSISTANT, content="Test response 2", chat_model=None),
    ]


def test_memory_creation_trigger(mem_op_ctx: ElroyContext, dummy_msgs: List[ContextMessage]):
    """
    Test that memory creation is triggered after a certain number of messages.

    This test verifies that:
    1. The messages_since_memory counter is incremented when messages are added
    2. When the counter exceeds the threshold, memory creation is triggered
    """
    # Get the current tracker state
    tracker = mem_op_ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == mem_op_ctx.user_id)).one_or_none()

    if not tracker:
        tracker = MemoryOperationTracker(user_id=mem_op_ctx.user_id, messages_since_memory=0)
        mem_op_ctx.db.add(tracker)
        mem_op_ctx.db.commit()
        mem_op_ctx.db.refresh(tracker)

    # Reset the counter to ensure we start from a known state
    tracker.messages_since_memory = 0
    mem_op_ctx.db.add(tracker)
    mem_op_ctx.db.commit()

    memory_ct = len(get_active_memories(mem_op_ctx))

    # Add messages one by one and check the counter

    for m in dummy_msgs:
        add_context_message(mem_op_ctx, m)

    tracker = get_or_create_memory_op_tracker(mem_op_ctx)
    assert tracker.messages_since_memory == 1

    assert len(get_active_memories(mem_op_ctx)) == memory_ct + 1


def test_memory_creation_batch_messages(ctx: ElroyContext, dummy_msgs: List[ContextMessage]):
    """
    Test that memory creation is triggered when adding multiple messages at once.

    This test verifies that:
    1. When adding multiple messages in a batch, the counter is incremented correctly
    2. Memory creation is triggered when the threshold is exceeded
    """
    memory_ct = len(get_active_memories(ctx))

    add_context_messages(ctx, dummy_msgs)

    assert (
        get_or_create_memory_op_tracker(ctx).messages_since_memory == 0
    )  # 0 rather than 1, since the memory creation op resets the tracker

    assert len(get_active_memories(ctx)) == memory_ct + 1


def test_other_memory_create_resets(mem_op_ctx: ElroyContext, dummy_msgs: List[ContextMessage]):
    mem_op_ctx.messages_between_memory = 3
    mem_op_ctx.use_background_threads = False

    memory_ct = len(get_active_memories(mem_op_ctx))
    add_context_messages(mem_op_ctx, dummy_msgs[:2])
    tracker = get_or_create_memory_op_tracker(mem_op_ctx)
    memory_ct = len(get_active_memories(mem_op_ctx))
    do_create_op_tracked_memory(mem_op_ctx, "Test memory", "Here's a test memory", [], tracker, False)
    new_memory_ct = len(get_active_memories(mem_op_ctx))
    assert new_memory_ct == memory_ct + 1

    add_context_messages(mem_op_ctx, dummy_msgs[2:])

    mem_op_ctx.db.refresh(tracker)
    assert tracker.messages_since_memory == 2
    assert len(get_active_memories(mem_op_ctx)) == new_memory_ct


def test_null_threshold(mem_op_ctx: ElroyContext, dummy_msgs: List[ContextMessage]):
    mem_op_ctx.messages_between_memory = None

    memory_ct = len(get_active_memories(mem_op_ctx))
    add_context_messages(mem_op_ctx, dummy_msgs * 30)
    assert len(get_active_memories(mem_op_ctx)) == memory_ct
