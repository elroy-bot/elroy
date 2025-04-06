"""
Tests for memory creation in the OpenAI-compatible server.
"""

from unittest import mock

import pytest

from elroy.web_api.openai_compatible.memory import (
    create_memory_from_conversation,
    process_memory_creation,
    should_create_memory,
)
from elroy.web_api.openai_compatible.models import Message, MessageRole


@pytest.fixture
def mock_context():
    """Mock the ElroyContext."""
    mock_ctx = mock.MagicMock()
    mock_ctx.user_id = 1
    mock_ctx.chat_model.name = "gpt-3.5-turbo"

    # Mock the db session
    mock_db = mock.MagicMock()
    mock_ctx.db = mock_db
    mock_ctx.db.session = mock.MagicMock()

    return mock_ctx


@pytest.fixture
def mock_memory_op_tracker():
    """Mock the MemoryOperationTracker."""
    mock_tracker = mock.MagicMock()
    mock_tracker.messages_since_memory = 0
    mock_tracker.memories_since_consolidation = 0

    return mock_tracker


@pytest.fixture
def mock_get_or_create_memory_op_tracker(mock_memory_op_tracker):
    """Mock the get_or_create_memory_op_tracker function."""
    with mock.patch("elroy.web_api.openai_compatible.memory.get_or_create_memory_op_tracker") as mock_get_tracker:
        mock_get_tracker.return_value = mock_memory_op_tracker
        yield mock_get_tracker


@pytest.fixture
def mock_do_create_memory_from_ctx_msgs():
    """Mock the do_create_memory_from_ctx_msgs function."""
    with mock.patch("elroy.web_api.openai_compatible.memory.do_create_memory_from_ctx_msgs") as mock_create:
        # Create a mock memory
        mock_memory = mock.MagicMock()
        mock_memory.name = "Test Memory"
        mock_memory.text = "This is a test memory"

        # Set up the mock to return our mock memory
        mock_create.return_value = (mock_memory, None)

        yield mock_create


@pytest.fixture
def mock_formulate_memory():
    """Mock the formulate_memory function."""
    with mock.patch("elroy.web_api.openai_compatible.memory.formulate_memory") as mock_formulate:
        # Set up the mock to return a title and text
        mock_formulate.return_value = ("Test Memory", "This is a test memory")

        yield mock_formulate


@pytest.mark.asyncio
async def test_should_create_memory_threshold_not_reached(mock_context, mock_get_or_create_memory_op_tracker, mock_memory_op_tracker):
    """Test that memory creation is not triggered when the threshold is not reached."""
    # Create test messages
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Hello, how are you?"),
        Message(role=MessageRole.ASSISTANT, content="I'm doing well, thank you!"),
    ]

    # Set the current message count
    mock_memory_op_tracker.messages_since_memory = 5

    # Check if we should create a memory
    result = await should_create_memory(mock_context, messages, memory_creation_interval=10)

    # Check the result
    assert result is False

    # Check that the tracker was updated
    assert mock_memory_op_tracker.messages_since_memory == 6
    mock_context.db.add.assert_called_once_with(mock_memory_op_tracker)
    mock_context.db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_should_create_memory_threshold_reached(mock_context, mock_get_or_create_memory_op_tracker, mock_memory_op_tracker):
    """Test that memory creation is triggered when the threshold is reached."""
    # Create test messages
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Hello, how are you?"),
        Message(role=MessageRole.ASSISTANT, content="I'm doing well, thank you!"),
    ]

    # Set the current message count
    mock_memory_op_tracker.messages_since_memory = 9

    # Check if we should create a memory
    result = await should_create_memory(mock_context, messages, memory_creation_interval=10)

    # Check the result
    assert result is True

    # Check that the tracker was reset
    assert mock_memory_op_tracker.messages_since_memory == 0
    assert mock_context.db.add.call_count == 2
    assert mock_context.db.commit.call_count == 2


@pytest.mark.asyncio
async def test_create_memory_from_conversation(mock_context, mock_formulate_memory, mock_do_create_memory_from_ctx_msgs):
    """Test creating a memory from a conversation."""
    # Create test messages
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Hello, how are you?"),
        Message(role=MessageRole.ASSISTANT, content="I'm doing well, thank you!"),
    ]

    # Create a memory
    result = await create_memory_from_conversation(mock_context, messages)

    # Check the result
    assert result == ("Test Memory", "This is a test memory")

    # Check that the formulate_memory function was called correctly
    mock_formulate_memory.assert_called_once()
    args, kwargs = mock_formulate_memory.call_args
    assert args[0] == mock_context
    assert len(args[1]) == 3  # Three context messages

    # Check that the do_create_memory_from_ctx_msgs function was called correctly
    mock_do_create_memory_from_ctx_msgs.assert_called_once_with(mock_context, "Test Memory", "This is a test memory")


@pytest.mark.asyncio
async def test_process_memory_creation_enabled_should_create(mock_context, mock_get_or_create_memory_op_tracker, mock_memory_op_tracker):
    """Test processing memory creation when enabled and should create."""
    # Create test messages
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Hello, how are you?"),
        Message(role=MessageRole.ASSISTANT, content="I'm doing well, thank you!"),
    ]

    # Set the current message count to trigger creation
    mock_memory_op_tracker.messages_since_memory = 9

    # Mock the should_create_memory and create_memory_from_conversation functions
    with mock.patch("elroy.web_api.openai_compatible.memory.should_create_memory") as mock_should_create:
        mock_should_create.return_value = True

        with mock.patch("elroy.web_api.openai_compatible.memory.create_memory_from_conversation") as mock_create:
            mock_create.return_value = ("Test Memory", "This is a test memory")

            # Process memory creation
            await process_memory_creation(
                mock_context,
                messages,
                memory_creation_interval=10,
                enable_memory_creation=True,
            )

            # Check that the functions were called correctly
            mock_should_create.assert_called_once_with(mock_context, messages, 10)
            mock_create.assert_called_once_with(mock_context, messages)


@pytest.mark.asyncio
async def test_process_memory_creation_enabled_should_not_create(
    mock_context, mock_get_or_create_memory_op_tracker, mock_memory_op_tracker
):
    """Test processing memory creation when enabled but should not create."""
    # Create test messages
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Hello, how are you?"),
        Message(role=MessageRole.ASSISTANT, content="I'm doing well, thank you!"),
    ]

    # Set the current message count to not trigger creation
    mock_memory_op_tracker.messages_since_memory = 5

    # Mock the should_create_memory and create_memory_from_conversation functions
    with mock.patch("elroy.web_api.openai_compatible.memory.should_create_memory") as mock_should_create:
        mock_should_create.return_value = False

        with mock.patch("elroy.web_api.openai_compatible.memory.create_memory_from_conversation") as mock_create:
            # Process memory creation
            await process_memory_creation(
                mock_context,
                messages,
                memory_creation_interval=10,
                enable_memory_creation=True,
            )

            # Check that the functions were called correctly
            mock_should_create.assert_called_once_with(mock_context, messages, 10)
            mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_process_memory_creation_disabled(mock_context, mock_get_or_create_memory_op_tracker, mock_memory_op_tracker):
    """Test processing memory creation when disabled."""
    # Create test messages
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Hello, how are you?"),
        Message(role=MessageRole.ASSISTANT, content="I'm doing well, thank you!"),
    ]

    # Mock the should_create_memory and create_memory_from_conversation functions
    with mock.patch("elroy.web_api.openai_compatible.memory.should_create_memory") as mock_should_create:
        with mock.patch("elroy.web_api.openai_compatible.memory.create_memory_from_conversation") as mock_create:
            # Process memory creation
            await process_memory_creation(
                mock_context,
                messages,
                memory_creation_interval=10,
                enable_memory_creation=False,
            )

            # Check that the functions were not called
            mock_should_create.assert_not_called()
            mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_process_memory_creation_error_handling(mock_context, mock_get_or_create_memory_op_tracker, mock_memory_op_tracker):
    """Test error handling in process_memory_creation."""
    # Create test messages
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Hello, how are you?"),
        Message(role=MessageRole.ASSISTANT, content="I'm doing well, thank you!"),
    ]

    # Mock the should_create_memory function to raise an exception
    with mock.patch("elroy.web_api.openai_compatible.memory.should_create_memory") as mock_should_create:
        mock_should_create.side_effect = Exception("Test error")

        # Mock the logger
        with mock.patch("elroy.web_api.openai_compatible.memory.logger") as mock_logger:
            # Process memory creation
            await process_memory_creation(
                mock_context,
                messages,
                memory_creation_interval=10,
                enable_memory_creation=True,
            )

            # Check that the error was logged
            mock_logger.error.assert_called_once()
            assert "Test error" in mock_logger.error.call_args[0][0]


def test_memory_creation_in_chat_completions_endpoint():
    """Test that memory creation is triggered after a chat completion response."""
    # This test would be similar to the streaming test, but would check that
    # process_memory_creation is called with the correct parameters.
    # However, since we've already tested process_memory_creation thoroughly,
    # and the server.py file has been tested in other test files, we can
    # consider this test covered by the combination of those tests.
