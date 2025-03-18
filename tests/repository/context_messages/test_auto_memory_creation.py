from unittest.mock import patch

from sqlmodel import select

from elroy.core.constants import ASSISTANT, USER
from elroy.core.ctx import ElroyContext
from elroy.db.db_models import MemoryOperationTracker
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.operations import add_context_messages
from elroy.repository.memories.operations import create_mem_from_current_context


def test_memory_creation_trigger(george_ctx: ElroyContext):
    """
    Test that memory creation is triggered after a certain number of messages.

    This test verifies that:
    1. The messages_since_memory counter is incremented when messages are added
    2. When the counter exceeds the threshold, memory creation is triggered
    """
    # Set a specific threshold for testing
    george_ctx.messages_between_memory = 3

    # Get the current tracker state
    tracker = george_ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == george_ctx.user_id)).one_or_none()

    if not tracker:
        tracker = MemoryOperationTracker(user_id=george_ctx.user_id, messages_since_memory=0)
        george_ctx.db.add(tracker)
        george_ctx.db.commit()
        george_ctx.db.refresh(tracker)

    # Reset the counter to ensure we start from a known state
    tracker.messages_since_memory = 0
    george_ctx.db.add(tracker)
    george_ctx.db.commit()

    # Mock the create_mem_from_current_context function to verify it's called
    with patch("elroy.repository.context_messages.operations.run_in_background") as mock_run_bg:
        # Add messages one by one and check the counter
        messages = [
            ContextMessage(role=USER, content="Test message 1", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Test response 1", chat_model=None),
            ContextMessage(role=USER, content="Test message 2", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Test response 2", chat_model=None),
        ]

        # Add first message - counter should be 1
        add_context_messages(george_ctx, [messages[0]])
        tracker = george_ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == george_ctx.user_id)).one()
        assert tracker.messages_since_memory == 1
        mock_run_bg.assert_not_called()

        # Add second message - counter should be 2
        add_context_messages(george_ctx, [messages[1]])
        tracker = george_ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == george_ctx.user_id)).one()
        assert tracker.messages_since_memory == 2
        mock_run_bg.assert_not_called()

        # Add third message - counter should be 3, which equals the threshold
        # Memory creation should be triggered
        add_context_messages(george_ctx, [messages[2]])
        tracker = george_ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == george_ctx.user_id)).one()
        assert tracker.messages_since_memory == 3
        mock_run_bg.assert_called_once_with(create_mem_from_current_context, george_ctx)

        # Reset the mock to check the next call
        mock_run_bg.reset_mock()

        # Add fourth message - counter should be reset to 1 after memory creation
        add_context_messages(george_ctx, [messages[3]])
        tracker = george_ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == george_ctx.user_id)).one()
        assert tracker.messages_since_memory == 1
        mock_run_bg.assert_not_called()


def test_memory_creation_batch_messages(george_ctx: ElroyContext):
    """
    Test that memory creation is triggered when adding multiple messages at once.

    This test verifies that:
    1. When adding multiple messages in a batch, the counter is incremented correctly
    2. Memory creation is triggered when the threshold is exceeded
    """
    # Set a specific threshold for testing
    george_ctx.messages_between_memory = 3

    # Get the current tracker state
    tracker = george_ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == george_ctx.user_id)).one_or_none()

    if not tracker:
        tracker = MemoryOperationTracker(user_id=george_ctx.user_id, messages_since_memory=0)
        george_ctx.db.add(tracker)
        george_ctx.db.commit()
        george_ctx.db.refresh(tracker)

    # Reset the counter to ensure we start from a known state
    tracker.messages_since_memory = 0
    george_ctx.db.add(tracker)
    george_ctx.db.commit()

    # Mock the create_mem_from_current_context function to verify it's called
    with patch("elroy.repository.context_messages.operations.run_in_background") as mock_run_bg:
        # Create a batch of messages that exceeds the threshold
        messages = [
            ContextMessage(role=USER, content="Batch test message 1", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Batch test response 1", chat_model=None),
            ContextMessage(role=USER, content="Batch test message 2", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Batch test response 2", chat_model=None),
        ]

        # Add all messages at once - counter should be 4, which exceeds the threshold
        # Memory creation should be triggered
        add_context_messages(george_ctx, messages)

        tracker = george_ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == george_ctx.user_id)).one()

        # Counter should be 4 (or equal to the number of user/assistant messages)
        assert tracker.messages_since_memory == 4

        # Memory creation should be triggered
        mock_run_bg.assert_called_once_with(create_mem_from_current_context, george_ctx)


def test_system_messages_not_counted(george_ctx: ElroyContext):
    """
    Test that system messages are not counted towards the memory creation threshold.

    This test verifies that:
    1. Only USER and ASSISTANT messages increment the counter
    2. SYSTEM messages do not affect the counter
    """
    # Set a specific threshold for testing
    george_ctx.messages_between_memory = 3

    # Get the current tracker state
    tracker = george_ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == george_ctx.user_id)).one_or_none()

    if not tracker:
        tracker = MemoryOperationTracker(user_id=george_ctx.user_id, messages_since_memory=0)
        george_ctx.db.add(tracker)
        george_ctx.db.commit()
        george_ctx.db.refresh(tracker)

    # Reset the counter to ensure we start from a known state
    tracker.messages_since_memory = 0
    george_ctx.db.add(tracker)
    george_ctx.db.commit()

    # Mock the create_mem_from_current_context function to verify it's called
    with patch("elroy.repository.context_messages.operations.run_in_background") as mock_run_bg:
        # Add a system message - counter should remain 0
        system_message = ContextMessage(role="system", content="System instruction", chat_model=None)
        add_context_messages(george_ctx, [system_message])

        tracker = george_ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == george_ctx.user_id)).one()

        # Counter should still be 0 since system messages don't count
        assert tracker.messages_since_memory == 0
        mock_run_bg.assert_not_called()

        # Add user and assistant messages to reach the threshold
        messages = [
            ContextMessage(role=USER, content="Test message 1", chat_model=None),
            ContextMessage(role=ASSISTANT, content="Test response 1", chat_model=None),
            ContextMessage(role=USER, content="Test message 2", chat_model=None),
        ]

        # Add all messages at once - counter should be 3, which equals the threshold
        add_context_messages(george_ctx, messages)

        tracker = george_ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == george_ctx.user_id)).one()

        # Counter should be 3 (only counting user/assistant messages)
        assert tracker.messages_since_memory == 3

        # Memory creation should be triggered
        mock_run_bg.assert_called_once_with(create_mem_from_current_context, george_ctx)
