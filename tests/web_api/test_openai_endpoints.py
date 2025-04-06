"""
Tests for the OpenAI-compatible server endpoints.
"""

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from elroy.web_api.openai_compatible.models import (
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatCompletionResponseMessage,
    MessageRole,
    UsageInfo,
)
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
def mock_conversation_tracker():
    """Mock the ConversationTracker class."""
    with mock.patch("elroy.web_api.openai_compatible.server.ConversationTracker") as mock_tracker_cls:
        # Create a mock tracker instance
        mock_tracker = mock.MagicMock()
        mock_tracker.compare_and_update_conversation.return_value = ([], False)

        # Set up the mock class to return our mock tracker
        mock_tracker_cls.return_value = mock_tracker

        yield mock_tracker


@pytest.fixture
def mock_get_relevant_memories():
    """Mock the get_relevant_memories_for_conversation function."""
    with mock.patch("elroy.web_api.openai_compatible.server.get_relevant_memories_for_conversation") as mock_get_memories:
        # Set up the mock to return an empty list
        mock_get_memories.return_value = []

        yield mock_get_memories


@pytest.fixture
def mock_generate_chat_completion():
    """Mock the generate_chat_completion function."""
    with mock.patch("elroy.web_api.openai_compatible.server.generate_chat_completion") as mock_generate:
        # Create a mock response
        mock_response = ChatCompletionResponse(
            id="chatcmpl-123",
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

        # Set up the mock to return our mock response
        mock_generate.return_value = mock_response

        yield mock_generate


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")

    assert response.status_code == 200
    assert "message" in response.json()
    assert "version" in response.json()
    assert "documentation" in response.json()


def test_models_endpoint(client):
    """Test the models endpoint."""
    response = client.get("/v1/models")

    assert response.status_code == 200
    assert response.json()["object"] == "list"
    assert "data" in response.json()
    assert len(response.json()["data"]) > 0
    assert "id" in response.json()["data"][0]
    assert "object" in response.json()["data"][0]
    assert "created" in response.json()["data"][0]
    assert "owned_by" in response.json()["data"][0]


def test_chat_completions_endpoint(
    client,
    mock_context,
    mock_conversation_tracker,
    mock_get_relevant_memories,
    mock_generate_chat_completion,
):
    """Test the chat completions endpoint."""
    # Create a test request
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ],
        "temperature": 0.7,
        "max_tokens": 100,
    }

    # Send the request
    response = client.post(
        "/v1/chat/completions",
        json=request_data,
    )

    # Check the response
    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-123"
    assert response.json()["model"] == "gpt-3.5-turbo"
    assert len(response.json()["choices"]) == 1
    assert response.json()["choices"][0]["message"]["role"] == "assistant"
    assert response.json()["choices"][0]["message"]["content"] == "This is a test response"
    assert response.json()["choices"][0]["finish_reason"] == "stop"
    assert response.json()["usage"]["prompt_tokens"] == 10
    assert response.json()["usage"]["completion_tokens"] == 10
    assert response.json()["usage"]["total_tokens"] == 20

    # Check that the mock functions were called correctly
    mock_conversation_tracker.compare_and_update_conversation.assert_called_once()
    mock_get_relevant_memories.assert_called_once()
    mock_generate_chat_completion.assert_called_once()


def test_chat_completions_invalid_request(client):
    """Test the chat completions endpoint with an invalid request."""
    # Create an invalid request (missing required fields)
    request_data = {
        "model": "gpt-3.5-turbo",
        # Missing messages field
    }

    # Send the request
    response = client.post(
        "/v1/chat/completions",
        json=request_data,
    )

    # Check the response
    assert response.status_code == 422  # Unprocessable Entity
    assert "detail" in response.json()


def test_chat_completions_streaming(
    client,
    mock_context,
    mock_conversation_tracker,
    mock_get_relevant_memories,
):
    """Test the chat completions endpoint with streaming enabled."""
    # Mock the stream_chat_completion function
    with mock.patch("elroy.web_api.openai_compatible.server.stream_chat_completion") as mock_stream:
        # Set up the mock to yield some test data
        mock_stream.return_value = [
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n\n',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"This"},"finish_reason":null}]}\n\n',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":" is"},"finish_reason":null}]}\n\n',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":" a"},"finish_reason":null}]}\n\n',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":" test"},"finish_reason":null}]}\n\n',
            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n',
            "data: [DONE]\n\n",
        ]

        # Create a test request with streaming enabled
        request_data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, how are you?"},
            ],
            "temperature": 0.7,
            "max_tokens": 100,
            "stream": True,
        }

        # Send the request
        response = client.post(
            "/v1/chat/completions",
            json=request_data,
        )

        # Check the response
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"

        # Parse the streaming response
        chunks = []
        for line in response.iter_lines():
            if line:
                chunks.append(line.decode())

        # Check that we got the expected chunks
        assert len(chunks) == 7
        assert chunks[0].startswith('data: {"id":"chatcmpl-123"')
        assert '"role":"assistant"' in chunks[0]
        assert '"content":"This"' in chunks[1]
        assert '"content":" is"' in chunks[2]
        assert '"content":" a"' in chunks[3]
        assert '"content":" test"' in chunks[4]
        assert '"finish_reason":"stop"' in chunks[5]
        assert chunks[6] == "data: [DONE]"

        # Check that the mock functions were called correctly
        mock_conversation_tracker.compare_and_update_conversation.assert_called_once()
        mock_get_relevant_memories.assert_called_once()
        mock_stream.assert_called_once()
