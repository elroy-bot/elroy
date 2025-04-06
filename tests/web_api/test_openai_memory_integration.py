"""
Tests for memory integration in the OpenAI-compatible server.
"""

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from elroy.db.db_models import Memory
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.web_api.openai_compatible.memory import (
    convert_context_message_to_openai_message,
    convert_openai_message_to_context_message,
    get_relevant_memories_for_conversation,
)
from elroy.web_api.openai_compatible.models import Message, MessageRole
from elroy.web_api.openai_compatible.server import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_context():
    """Mock the get_context function to return a test context."""
    with mock.patch("elroy.web_api.openai_compatible.server.get_context") as mock_get_context:
        # Create a mock context that will be returned by get_context
        mock_ctx = mock.MagicMock()
        mock_ctx.user_id = 1
        mock_ctx.chat_model.name = "gpt-3.5-turbo"

        # Mock the db session
        mock_db = mock.MagicMock()
        mock_ctx.db = mock_db
        mock_ctx.db.session = mock.MagicMock()

        # Set up the mock to return our mock context
        mock_get_context.return_value = mock_ctx

        yield mock_ctx


@pytest.fixture
def mock_get_relevant_memories():
    """Mock the get_relevant_memories function."""
    with mock.patch("elroy.repository.memories.queries.get_relevant_memories") as mock_get_memories:
        # Create some mock memories
        mock_memory1 = Memory(
            id=1,
            user_id=1,
            name="Test Memory 1",
            text="This is test memory 1",
            is_active=True,
        )
        mock_memory2 = Memory(
            id=2,
            user_id=1,
            name="Test Memory 2",
            text="This is test memory 2",
            is_active=True,
        )

        # Set up the mock to return our mock memories
        mock_get_memories.return_value = [mock_memory1, mock_memory2]

        yield mock_get_memories


def test_convert_openai_message_to_context_message():
    """Test converting an OpenAI message to a context message."""
    # Create a test OpenAI message
    openai_message = Message(
        role=MessageRole.USER,
        content="Hello, how are you?",
    )

    # Convert to a context message
    context_message = convert_openai_message_to_context_message(openai_message, "gpt-3.5-turbo")

    # Check the conversion
    assert context_message.role == "user"
    assert context_message.content == "Hello, how are you?"
    assert context_message.chat_model == "gpt-3.5-turbo"
    assert context_message.tool_calls is None
    assert context_message.tool_call_id is None


def test_convert_context_message_to_openai_message():
    """Test converting a context message to an OpenAI message."""
    # Create a test context message
    context_message = ContextMessage(
        role="assistant",
        content="I'm doing well, thank you!",
        chat_model="gpt-3.5-turbo",
    )

    # Convert to an OpenAI message
    openai_message = convert_context_message_to_openai_message(context_message)

    # Check the conversion
    assert openai_message.role == MessageRole.ASSISTANT
    assert openai_message.content == "I'm doing well, thank you!"
    assert openai_message.tool_calls is None
    assert openai_message.tool_call_id is None


@pytest.fixture
def mock_get_embedding():
    """Mock the get_embedding function."""
    with mock.patch("elroy.repository.memories.queries.get_embedding") as mock_get_embedding:
        # Set up the mock to return a fixed embedding
        mock_get_embedding.return_value = [0.1] * 1536  # OpenAI embeddings are 1536-dimensional
        yield mock_get_embedding


@pytest.mark.asyncio
async def test_get_relevant_memories_for_conversation(mock_context, mock_get_relevant_memories, mock_get_embedding):
    """Test retrieving relevant memories for a conversation."""
    # Create test messages
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Hello, how are you?"),
        Message(role=MessageRole.ASSISTANT, content="I'm doing well, thank you!"),
        Message(role=MessageRole.USER, content="Tell me about memory."),
    ]

    # Mock the get_relevant_memories_for_conversation function directly
    with mock.patch("elroy.web_api.openai_compatible.memory.get_relevant_memories") as mock_get_memories:
        # Set up the mock to return our mock memories
        mock_memory1 = Memory(
            id=1,
            user_id=1,
            name="Test Memory 1",
            text="This is test memory 1",
            is_active=True,
        )
        mock_memory2 = Memory(
            id=2,
            user_id=1,
            name="Test Memory 2",
            text="This is test memory 2",
            is_active=True,
        )
        mock_get_memories.return_value = [mock_memory1, mock_memory2]

        # Get relevant memories
        memories = await get_relevant_memories_for_conversation(
            mock_context,
            messages,
            max_memories=5,
            relevance_threshold=0.7,
        )

        # Check the result
        assert len(memories) == 2
        assert memories[0].name == "Test Memory 1"

        # Use to_fact() for Memory objects or get a string representation
        memory_content = memories[0].to_fact() if hasattr(memories[0], "to_fact") else str(memories[0])
        assert "This is test memory 1" in memory_content

        assert memories[1].name == "Test Memory 2"
        memory_content = memories[1].to_fact() if hasattr(memories[1], "to_fact") else str(memories[1])
        assert "This is test memory 2" in memory_content

        # Check that the mock was called correctly
        mock_get_memories.assert_called_once()


@pytest.mark.asyncio
async def test_get_relevant_memories_for_conversation_no_user_messages(mock_context, mock_get_relevant_memories):
    """Test retrieving relevant memories when there are no user messages."""
    # Create test messages with no user messages
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.ASSISTANT, content="I'm doing well, thank you!"),
    ]

    # Get relevant memories
    memories = await get_relevant_memories_for_conversation(
        mock_context,
        messages,
        max_memories=5,
        relevance_threshold=0.7,
    )

    # Check the result
    assert len(memories) == 0

    # Check that the mock was not called
    mock_get_relevant_memories.assert_not_called()


@pytest.mark.asyncio
async def test_get_relevant_memories_for_conversation_empty_content(mock_context, mock_get_relevant_memories):
    """Test retrieving relevant memories when user messages have empty content."""
    # Create test messages with empty content
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content=None),
        Message(role=MessageRole.ASSISTANT, content="I'm not sure what you mean."),
    ]

    # Get relevant memories
    memories = await get_relevant_memories_for_conversation(
        mock_context,
        messages,
        max_memories=5,
        relevance_threshold=0.7,
    )

    # Check the result
    assert len(memories) == 0

    # Check that the mock was not called
    mock_get_relevant_memories.assert_not_called()


def test_memory_augmentation_in_chat_completions(client, mock_context, mock_get_relevant_memories, mock_get_embedding):
    """Test that memories are included in the context for chat completions."""
    # Import the models at the top level
    from elroy.web_api.openai_compatible.models import (
        ChatCompletionResponse,
        ChatCompletionResponseChoice,
        ChatCompletionResponseMessage,
        MessageRole,
        UsageInfo,
    )

    # Create a proper mock response
    mock_response = ChatCompletionResponse(
        id="chatcmpl-123",
        object="chat.completion",
        model="gpt-3.5-turbo",
        choices=[
            ChatCompletionResponseChoice(
                index=0,
                message=ChatCompletionResponseMessage(
                    role=MessageRole.ASSISTANT,
                    content="This is a test response",
                ),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
        ),
    )

    # Set up all the mocks
    with (
        mock.patch("elroy.web_api.openai_compatible.server.ConversationTracker") as mock_tracker_cls,
        mock.patch("elroy.web_api.openai_compatible.server.get_relevant_memories_for_conversation") as mock_get_memories_for_conversation,
        mock.patch("elroy.core.ctx.ElroyContext.user_id", new_callable=mock.PropertyMock) as mock_user_id,
        mock.patch("elroy.web_api.openai_compatible.server.get_assistant_name") as mock_get_assistant_name,
        mock.patch("elroy.web_api.openai_compatible.server.do_get_user_preferred_name") as mock_get_user_preferred_name,
        mock.patch("elroy.web_api.openai_compatible.server.generate_chat_completion") as mock_generate,
    ):

        # Set up the mock tracker
        mock_tracker = mock.MagicMock()
        mock_tracker.compare_and_update_conversation.return_value = (
            [
                ContextMessage(
                    role="system",
                    content="You are a helpful assistant.",
                    chat_model="gpt-3.5-turbo",
                ),
                ContextMessage(
                    role="user",
                    content="Tell me about memory.",
                    chat_model="gpt-3.5-turbo",
                ),
            ],
            False,
        )
        mock_tracker_cls.return_value = mock_tracker

        # Set up the mock memories
        mock_memory1 = Memory(
            id=1,
            user_id=1,
            name="Test Memory 1",
            text="This is test memory 1",
            is_active=True,
        )
        mock_memory2 = Memory(
            id=2,
            user_id=1,
            name="Test Memory 2",
            text="This is test memory 2",
            is_active=True,
        )
        mock_get_memories_for_conversation.return_value = [mock_memory1, mock_memory2]

        # Set up other mocks
        mock_user_id.return_value = 1
        mock_get_assistant_name.return_value = "Test Assistant"
        mock_get_user_preferred_name.return_value = "Test User"
        mock_generate.return_value = mock_response

        # Create a test request
        request_data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Tell me about memory."},
            ],
        }

        # Send the request
        response = client.post(
            "/v1/chat/completions",
            json=request_data,
        )

        # Check the response
        assert response.status_code == 200

        # Check that the generate_chat_completion function was called
        mock_generate.assert_called_once()

        # Check that the get_relevant_memories_for_conversation function was called
        mock_get_memories_for_conversation.assert_called_once()
