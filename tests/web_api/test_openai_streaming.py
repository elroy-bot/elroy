"""
Tests for streaming support in the OpenAI-compatible server.
"""

import json
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from elroy.repository.context_messages.data_models import ContextMessage
from elroy.web_api.openai_compatible.server import app, stream_chat_completion


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


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
def mock_generate_chat_completion_message():
    """Mock the generate_chat_completion_message function."""
    with mock.patch("elroy.web_api.openai_compatible.server.generate_chat_completion_message") as mock_generate:
        # Create a mock stream parser
        mock_parser = mock.MagicMock()

        # Set up the mock to return our mock parser
        mock_generate.return_value = mock_parser

        yield mock_generate, mock_parser


@pytest.mark.asyncio
async def test_stream_chat_completion(mock_context, mock_generate_chat_completion_message):
    """Test streaming chat completions."""
    mock_generate, mock_parser = mock_generate_chat_completion_message

    # Set up the mock parser to yield chunks with content
    class MockChunk:
        def __init__(self, content):
            self.content = content

    mock_parser.process_stream.return_value = [
        MockChunk("Hello"),
        MockChunk(", "),
        MockChunk("world"),
        MockChunk("!"),
    ]

    # Create test request and context messages
    request = mock.MagicMock()
    request.model = "gpt-3.5-turbo"

    context_messages = [
        ContextMessage(
            role="system",
            content="You are a helpful assistant.",
            chat_model="gpt-3.5-turbo",
        ),
        ContextMessage(
            role="user",
            content="Say hello world",
            chat_model="gpt-3.5-turbo",
        ),
    ]

    # Call the function
    stream_generator = stream_chat_completion(
        mock_context,
        request,
        context_messages,
        enable_memory_creation=True,
        memory_creation_interval=10,
    )

    # Collect the chunks
    chunks = []
    async for chunk in stream_generator:
        chunks.append(chunk)

    # Check the results
    assert len(chunks) == 7  # 1 role chunk + 4 content chunks + 1 finish chunk + 1 [DONE] chunk

    # Parse the chunks
    parsed_chunks = []
    for chunk in chunks:
        if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
            data = json.loads(chunk[6:].strip())
            parsed_chunks.append(data)

    # Check the first chunk (role)
    assert parsed_chunks[0]["choices"][0]["delta"]["role"] == "assistant"

    # Check the content chunks
    assert parsed_chunks[1]["choices"][0]["delta"]["content"] == "Hello"
    assert parsed_chunks[2]["choices"][0]["delta"]["content"] == ", "
    assert parsed_chunks[3]["choices"][0]["delta"]["content"] == "world"
    assert parsed_chunks[4]["choices"][0]["delta"]["content"] == "!"

    # Check the finish chunk
    assert parsed_chunks[5]["choices"][0]["finish_reason"] == "stop"
    assert "delta" in parsed_chunks[5]["choices"][0]
    assert parsed_chunks[5]["choices"][0]["delta"] == {}

    # Check that the last chunk is [DONE]
    assert chunks[-1] == "data: [DONE]\n\n"

    # Check that the generate_chat_completion_message function was called correctly
    mock_generate.assert_called_once_with(
        mock_context.chat_model,
        context_messages,
        [],  # No tools
        enable_tools=False,
    )


def test_streaming_endpoint(client, mock_context, mock_generate_chat_completion_message):
    """Test the streaming endpoint."""
    mock_generate, mock_parser = mock_generate_chat_completion_message

    # Set up the mock parser to yield chunks with content
    class MockChunk:
        def __init__(self, content):
            self.content = content

    mock_parser.process_stream.return_value = [
        MockChunk("Hello"),
        MockChunk(", "),
        MockChunk("world"),
        MockChunk("!"),
    ]

    # Mock the get_context function
    with mock.patch("elroy.web_api.openai_compatible.server.get_context") as mock_get_context:
        mock_get_context.return_value = mock_context

        # Mock the conversation tracker
        with mock.patch("elroy.web_api.openai_compatible.server.ConversationTracker") as mock_tracker_cls:
            # Create a mock tracker instance
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
                        content="Say hello world",
                        chat_model="gpt-3.5-turbo",
                    ),
                ],
                False,
            )

            # Set up the mock class to return our mock tracker
            mock_tracker_cls.return_value = mock_tracker

            # Mock the get_relevant_memories_for_conversation function
            with mock.patch("elroy.web_api.openai_compatible.server.get_relevant_memories_for_conversation") as mock_get_memories:
                # Set up the mock to return an empty list
                mock_get_memories.return_value = []

                # Create a test request
                request_data = {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Say hello world"},
                    ],
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
                assert len(chunks) == 7  # 1 role chunk + 4 content chunks + 1 finish chunk + 1 [DONE] chunk

                # Check the first chunk (role)
                assert "role" in chunks[0]
                assert "assistant" in chunks[0]

                # Check the content chunks
                assert "Hello" in chunks[1]
                assert ", " in chunks[2]
                assert "world" in chunks[3]
                assert "!" in chunks[4]

                # Check the finish chunk
                assert "finish_reason" in chunks[5]
                assert "stop" in chunks[5]

                # Check that the last chunk is [DONE]
                assert chunks[-1] == "data: [DONE]"


def test_streaming_vs_non_streaming_content(client, mock_context):
    """Test that streaming and non-streaming responses match in content."""
    # Mock the get_context function
    with mock.patch("elroy.web_api.openai_compatible.server.get_context") as mock_get_context:
        mock_get_context.return_value = mock_context

        # Mock the conversation tracker
        with mock.patch("elroy.web_api.openai_compatible.server.ConversationTracker") as mock_tracker_cls:
            # Create a mock tracker instance
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
                        content="Say hello world",
                        chat_model="gpt-3.5-turbo",
                    ),
                ],
                False,
            )

            # Set up the mock class to return our mock tracker
            mock_tracker_cls.return_value = mock_tracker

            # Mock the get_relevant_memories_for_conversation function
            with mock.patch("elroy.web_api.openai_compatible.server.get_relevant_memories_for_conversation") as mock_get_memories:
                # Set up the mock to return an empty list
                mock_get_memories.return_value = []

                # Mock the generate_chat_completion function for non-streaming
                with mock.patch("elroy.web_api.openai_compatible.server.generate_chat_completion") as mock_generate:
                    # Create a mock response
                    mock_response = mock.MagicMock()
                    mock_response.choices[0].message.content = "Hello, world!"

                    # Set up the mock to return our mock response
                    mock_generate.return_value = mock_response

                    # Mock the stream_chat_completion function for streaming
                    with mock.patch("elroy.web_api.openai_compatible.server.stream_chat_completion") as mock_stream:
                        # Set up the mock to yield chunks that combine to the same content
                        mock_stream.return_value = [
                            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n\n',
                            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n\n',
                            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":", "},"finish_reason":null}]}\n\n',
                            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"world"},"finish_reason":null}]}\n\n',
                            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}\n\n',
                            'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-3.5-turbo","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n',
                            "data: [DONE]\n\n",
                        ]

                        # Create a test request for non-streaming
                        non_streaming_request = {
                            "model": "gpt-3.5-turbo",
                            "messages": [
                                {"role": "system", "content": "You are a helpful assistant."},
                                {"role": "user", "content": "Say hello world"},
                            ],
                            "stream": False,
                        }

                        # Send the non-streaming request
                        non_streaming_response = client.post(
                            "/v1/chat/completions",
                            json=non_streaming_request,
                        )

                        # Create a test request for streaming
                        streaming_request = {
                            "model": "gpt-3.5-turbo",
                            "messages": [
                                {"role": "system", "content": "You are a helpful assistant."},
                                {"role": "user", "content": "Say hello world"},
                            ],
                            "stream": True,
                        }

                        # Send the streaming request
                        streaming_response = client.post(
                            "/v1/chat/completions",
                            json=streaming_request,
                        )

                        # Extract the content from the non-streaming response
                        non_streaming_content = non_streaming_response.json()["choices"][0]["message"]["content"]

                        # Extract the content from the streaming response
                        streaming_content = ""
                        for line in streaming_response.iter_lines():
                            if line:
                                chunk = line.decode()
                                if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                                    data = json.loads(chunk[6:].strip())
                                    if "content" in data["choices"][0]["delta"]:
                                        streaming_content += data["choices"][0]["delta"]["content"]

                        # Check that the content matches
                        assert non_streaming_content == "Hello, world!"
                        assert streaming_content == "Hello, world!"
