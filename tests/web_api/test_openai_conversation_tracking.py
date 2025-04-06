"""
Tests for conversation tracking in the OpenAI-compatible server.
"""

from unittest import mock

import pytest

from elroy.repository.context_messages.data_models import ContextMessage
from elroy.web_api.openai_compatible.conversation import ConversationTracker
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
def mock_context_message_set():
    """Mock the ContextMessageSet."""
    mock_set = mock.MagicMock()
    mock_set.messages_list = []

    return mock_set


@pytest.fixture
def mock_get_or_create_context_message_set(mock_context_message_set):
    """Mock the get_or_create_context_message_set function."""
    with mock.patch("elroy.web_api.openai_compatible.conversation.get_or_create_context_message_set") as mock_get_set:
        mock_get_set.return_value = mock_context_message_set
        yield mock_get_set


def test_conversation_tracker_init(mock_context, mock_get_or_create_context_message_set):
    """Test initializing the ConversationTracker."""
    tracker = ConversationTracker(mock_context)

    assert tracker.ctx == mock_context
    assert tracker.context_message_set == mock_get_or_create_context_message_set.return_value
    mock_get_or_create_context_message_set.assert_called_once_with(mock_context)


def test_get_stored_messages(mock_context, mock_get_or_create_context_message_set, mock_context_message_set):
    """Test getting stored messages."""
    # Set up mock messages
    mock_messages = [
        ContextMessage(
            role="system",
            content="You are a helpful assistant.",
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="user",
            content="Hello, how are you?",
            chat_model="gpt-3.5-turbo",
        ),
    ]
    mock_context_message_set.messages_list = mock_messages

    # Create the tracker and get stored messages
    tracker = ConversationTracker(mock_context)
    stored_messages = tracker.get_stored_messages()

    # Check the result
    assert stored_messages == mock_messages


def test_compare_and_update_conversation_no_stored_messages(mock_context, mock_get_or_create_context_message_set, mock_context_message_set):
    """Test comparing and updating when there are no stored messages."""
    # Set up empty stored messages
    mock_context_message_set.messages_list = []

    # Create the tracker
    tracker = ConversationTracker(mock_context)

    # Set up mock for _store_messages
    tracker._store_messages = mock.MagicMock()

    # Create test incoming messages
    incoming_messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Hello, how are you?"),
    ]

    # Compare and update
    result_messages, diverged = tracker.compare_and_update_conversation(incoming_messages)

    # Check the result
    assert not diverged
    assert len(result_messages) == 2
    assert result_messages[0].role == "system"
    assert result_messages[0].content == "You are a helpful assistant."
    assert result_messages[1].role == "user"
    assert result_messages[1].content == "Hello, how are you?"

    # Check that _store_messages was called
    tracker._store_messages.assert_called_once()
    # The first argument should be a list of ContextMessage objects
    args, kwargs = tracker._store_messages.call_args
    assert len(args[0]) == 2
    assert isinstance(args[0][0], ContextMessage)
    assert args[0][0].role == "system"
    assert args[0][0].content == "You are a helpful assistant."
    assert isinstance(args[0][1], ContextMessage)
    assert args[0][1].role == "user"
    assert args[0][1].content == "Hello, how are you?"


def test_compare_and_update_conversation_no_divergence(mock_context, mock_get_or_create_context_message_set, mock_context_message_set):
    """Test comparing and updating when there is no divergence."""
    # Set up stored messages
    stored_messages = [
        ContextMessage(
            role="system",
            content="You are a helpful assistant.",
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="user",
            content="Hello, how are you?",
            chat_model="gpt-3.5-turbo",
        ),
    ]
    mock_context_message_set.messages_list = stored_messages

    # Create the tracker
    tracker = ConversationTracker(mock_context)

    # Set up mocks
    tracker._append_messages = mock.MagicMock()
    tracker._find_divergence_index = mock.MagicMock(return_value=None)

    # Create test incoming messages (same as stored, plus one new)
    incoming_messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Hello, how are you?"),
        Message(role=MessageRole.ASSISTANT, content="I'm doing well, thank you!"),
    ]

    # Compare and update
    result_messages, diverged = tracker.compare_and_update_conversation(incoming_messages)

    # Check the result
    assert not diverged

    # Check that _append_messages was called with the new message
    tracker._append_messages.assert_called_once()
    args, kwargs = tracker._append_messages.call_args
    assert len(args[0]) == 1
    assert isinstance(args[0][0], ContextMessage)
    assert args[0][0].role == "assistant"
    assert args[0][0].content == "I'm doing well, thank you!"


def test_compare_and_update_conversation_with_divergence(mock_context, mock_get_or_create_context_message_set, mock_context_message_set):
    """Test comparing and updating when there is divergence."""
    # Set up stored messages
    stored_messages = [
        ContextMessage(
            role="system",
            content="You are a helpful assistant.",
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="user",
            content="Hello, how are you?",
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="assistant",
            content="I'm doing well, thank you!",
            chat_model="gpt-3.5-turbo",
        ),
    ]
    mock_context_message_set.messages_list = stored_messages

    # Create the tracker
    tracker = ConversationTracker(mock_context)

    # Set up mocks
    tracker._update_messages_after_divergence = mock.MagicMock()
    # Divergence at index 1 (the user message)
    tracker._find_divergence_index = mock.MagicMock(return_value=1)

    # Create test incoming messages (with different user message)
    incoming_messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="What's the weather like today?"),  # Different
        Message(role=MessageRole.ASSISTANT, content="I don't have access to weather information."),
    ]

    # Compare and update
    result_messages, diverged = tracker.compare_and_update_conversation(incoming_messages)

    # Check the result
    assert diverged

    # Check that _update_messages_after_divergence was called
    tracker._update_messages_after_divergence.assert_called_once()
    args, kwargs = tracker._update_messages_after_divergence.call_args
    assert args[0] == 1  # Divergence index
    assert len(args[1]) == 2  # New messages from divergence point
    assert args[1][0].role == "user"
    assert args[1][0].content == "What's the weather like today?"
    assert args[1][1].role == "assistant"
    assert args[1][1].content == "I don't have access to weather information."


def test_find_divergence_index():
    """Test finding the divergence index."""
    # Create a tracker with a mock context
    mock_ctx = mock.MagicMock()
    tracker = ConversationTracker(mock_ctx)

    # Create test stored messages
    stored_messages = [
        ContextMessage(
            role="system",
            content="You are a helpful assistant.",
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="user",
            content="Hello, how are you?",
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="assistant",
            content="I'm doing well, thank you!",
            chat_model="gpt-3.5-turbo",
        ),
    ]

    # Test 1: No divergence
    incoming_messages = [
        ContextMessage(
            role="system",
            content="You are a helpful assistant.",
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="user",
            content="Hello, how are you?",
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="assistant",
            content="I'm doing well, thank you!",
            chat_model="gpt-3.5-turbo",
        ),
    ]

    divergence_index = tracker._find_divergence_index(stored_messages, incoming_messages)
    assert divergence_index is None

    # Test 2: Divergence in the middle
    incoming_messages = [
        ContextMessage(
            role="system",
            content="You are a helpful assistant.",
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="user",
            content="What's the weather like today?",  # Different
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="assistant",
            content="I don't have access to weather information.",  # Different
            chat_model="gpt-3.5-turbo",
        ),
    ]

    divergence_index = tracker._find_divergence_index(stored_messages, incoming_messages)
    assert divergence_index == 1

    # Test 3: Divergence at the beginning
    incoming_messages = [
        ContextMessage(
            role="system",
            content="You are a friendly assistant.",  # Different
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="user",
            content="Hello, how are you?",
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="assistant",
            content="I'm doing well, thank you!",
            chat_model="gpt-3.5-turbo",
        ),
    ]

    divergence_index = tracker._find_divergence_index(stored_messages, incoming_messages)
    assert divergence_index == 0
