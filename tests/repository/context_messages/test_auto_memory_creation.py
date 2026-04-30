import pytest
from sqlmodel import select

from elroy.core.constants import ASSISTANT, USER
from elroy.core.ctx import ElroyConfig
from elroy.core.session import open_turn_context
from elroy.db.db_models import MemoryOperationTracker
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.factory import build_context_refresh_orchestrator
from elroy.repository.context_messages.session import build_context_message_session
from elroy.repository.memories.factory import build_memory_lifecycle_orchestrator, get_or_create_memory_op_tracker
from elroy.repository.memories.queries import get_active_memories
from elroy.repository.user.session import build_user_session


@pytest.fixture(scope="function")
def mem_op_ctx(ctx: ElroyConfig):
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
        ContextMessage(role=USER, content="Test message 3", chat_model=None),
        ContextMessage(role=ASSISTANT, content="Test response 3", chat_model=None),
        ContextMessage(role=USER, content="Test message 4", chat_model=None),
        ContextMessage(role=ASSISTANT, content="Test response 4", chat_model=None),
    ]


def test_memory_creation_trigger(mem_op_ctx: ElroyConfig, dummy_msgs: list[ContextMessage]):
    """
    Test that memory creation is triggered after a certain number of messages.

    This test verifies that:
    1. The messages_since_memory counter is incremented when messages are added
    2. When the counter exceeds the threshold, memory creation is triggered
    """
    # Get the current tracker state
    with open_turn_context(mem_op_ctx) as turn:
        user_session = build_user_session(turn)
        db_session = user_session.db
        user_id = user_session.user_id
        tracker = db_session.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == user_id)).one_or_none()

        if not tracker:
            tracker = db_session.persist(MemoryOperationTracker(user_id=user_id, messages_since_memory=0))
        else:
            tracker.messages_since_memory = 0
            db_session.add(tracker)
            db_session.commit()
            db_session.refresh(tracker)

    memory_ct = len(get_active_memories(mem_op_ctx))
    with open_turn_context(mem_op_ctx) as turn:
        context_refresh_orchestrator = build_context_refresh_orchestrator(build_context_message_session(turn))

        # Add messages one by one and check the counter

        for m in dummy_msgs:
            context_refresh_orchestrator.add_context_message(m)

    with open_turn_context(mem_op_ctx) as turn:
        tracker = get_or_create_memory_op_tracker(turn)
    assert tracker.messages_since_memory == 1

    assert len(get_active_memories(mem_op_ctx)) == memory_ct + 1


def test_memory_creation_batch_messages(mem_op_ctx: ElroyConfig, dummy_msgs: list[ContextMessage]):
    """
    Test that memory creation is triggered when adding multiple messages at once.

    This test verifies that:
    1. When adding multiple messages in a batch, the counter is incremented correctly
    2. Memory creation is triggered when the threshold is exceeded
    """
    memory_ct = len(get_active_memories(mem_op_ctx))

    with open_turn_context(mem_op_ctx) as turn:
        build_context_refresh_orchestrator(build_context_message_session(turn)).add_context_messages(dummy_msgs)

    with open_turn_context(mem_op_ctx) as turn:
        assert (
            get_or_create_memory_op_tracker(turn).messages_since_memory == 0
        )  # 0 rather than 1, since the memory creation op resets the tracker

    assert len(get_active_memories(mem_op_ctx)) == memory_ct + 1


def test_other_memory_create_resets(mem_op_ctx: ElroyConfig, dummy_msgs: list[ContextMessage]):
    mem_op_ctx.messages_between_memory = 3
    mem_op_ctx.use_background_threads = False

    memory_ct = len(get_active_memories(mem_op_ctx))
    with open_turn_context(mem_op_ctx) as turn:
        build_context_refresh_orchestrator(build_context_message_session(turn)).add_context_messages(dummy_msgs[:2])
        tracker = get_or_create_memory_op_tracker(turn)
    memory_ct = len(get_active_memories(mem_op_ctx))
    with open_turn_context(mem_op_ctx) as turn:
        build_memory_lifecycle_orchestrator(turn).do_create_op_tracked_memory("Test memory", "Here's a test memory", [], False)
    new_memory_ct = len(get_active_memories(mem_op_ctx))
    assert new_memory_ct == memory_ct + 1

    with open_turn_context(mem_op_ctx) as turn:
        build_context_refresh_orchestrator(build_context_message_session(turn)).add_context_messages(dummy_msgs[-4:])

    with open_turn_context(mem_op_ctx) as turn:
        tracker = get_or_create_memory_op_tracker(turn)
    assert tracker.messages_since_memory == 2
    assert len(get_active_memories(mem_op_ctx)) == new_memory_ct
