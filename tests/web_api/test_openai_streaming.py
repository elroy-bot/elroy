import json
import time
from typing import Any, Dict, List, Optional, Union
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

from elroy.core.ctx import ElroyContext
from elroy.web_api.openai_compatible.litellm_provider import ElroyLiteLLMProvider

# Create a test-specific version of the app
app = FastAPI(
    title="Elroy OpenAI-Compatible API Test",
    description="Test version of the OpenAI-compatible API",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Define the same models as in the server
class ChatCompletionMessage(BaseModel):
    role: str
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatCompletionMessage]
    temperature: float = 0.7
    top_p: float = 1.0
    n: int = 1
    stream: bool = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None


# Mock provider for testing
class MockProvider:
    def __init__(self):
        self.completion_response = None
        self.streaming_response = None
        self.error = None

    def set_completion_response(self, response):
        self.completion_response = response

    def set_streaming_response(self, response):
        self.streaming_response = response

    def set_error(self, error):
        self.error = error

    def completion(self, model, messages, **kwargs):
        if self.error:
            raise self.error
        return self.completion_response

    def streaming(self, model, messages, **kwargs):
        if self.error:
            raise self.error
        return self.streaming_response


# Global mock provider
mock_provider = MockProvider()


# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Elroy OpenAI-Compatible API",
        "version": "0.1.0",
        "description": "An OpenAI-compatible API that augments chat completion requests with memories",
    }


# Health endpoint
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


# Chat completions endpoint
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    try:
        if request.stream:
            # Return streaming response
            async def stream_generator():
                try:
                    streaming_response = mock_provider.streaming(request.model, request.messages)
                    if streaming_response:
                        for chunk in streaming_response:
                            yield f"data: {chunk}\n\n"
                    else:
                        yield "data: {}\n\n"
                except Exception as e:
                    # Handle errors within the stream generator
                    error_json = {"error": {"message": str(e), "type": "internal_server_error"}}
                    yield f"data: {json.dumps(error_json)}\n\n"

                # End the stream
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream",
            )
        else:
            # Return non-streaming response
            return mock_provider.completion(request.model, request.messages)
    except Exception as e:
        # Handle errors
        error_json = {"error": {"message": str(e), "type": "internal_server_error"}}
        if request.stream:

            async def error_stream():
                yield f"data: {json.dumps(error_json)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(error_stream(), media_type="text/event-stream")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": {"message": str(e), "type": "internal_server_error"}},
            )


# Test client
@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_ctx():
    """Create a mock ElroyContext for testing."""
    ctx = MagicMock(spec=ElroyContext)
    ctx.user_id = 1
    ctx.chat_model.name = "test-model"
    return ctx


@pytest.fixture
def provider(mock_ctx):
    """Create an ElroyLiteLLMProvider instance for testing."""
    return ElroyLiteLLMProvider(
        ctx=mock_ctx,
        enable_memory_creation=True,
        memory_creation_interval=10,
        max_memories_per_request=5,
    )


class TestOpenAIStreaming:
    """Tests for the streaming functionality in the OpenAI-compatible API."""

    def test_streaming_response_format(self, client):
        """Test that streaming responses are correctly formatted."""
        # Mock streaming response chunks
        chunk1 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}'
        chunk2 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}'
        chunk3 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}'
        chunk4 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'

        # Set up the mock to return our test chunks
        mock_provider.set_streaming_response([chunk1, chunk2, chunk3, chunk4])
        mock_provider.set_error(None)

        # Make the request
        request_data = {"model": "test-model", "messages": [{"role": "user", "content": "Hello"}], "stream": True}
        response = client.post("/v1/chat/completions", json=request_data)

        # Check the response
        assert response.status_code == 200

        # Collect the streaming response
        chunks = []
        for chunk in response.iter_lines():
            if chunk:
                chunks.append(chunk)

        # Check that we got the expected chunks in SSE format
        assert len(chunks) == 5  # 4 chunks + [DONE]
        assert chunks[0] == f"data: {chunk1}"
        assert chunks[1] == f"data: {chunk2}"
        assert chunks[2] == f"data: {chunk3}"
        assert chunks[3] == f"data: {chunk4}"
        assert chunks[4] == "data: [DONE]"

    @patch("litellm.completion")
    def test_streaming_vs_non_streaming_content(self, mock_completion, provider):
        """Test that streaming and non-streaming responses have the same content."""
        # Mock non-streaming response
        non_streaming_response = {
            "id": "test-id",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello world"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }

        # Mock streaming response chunks
        chunk1 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}'
        chunk2 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}'
        chunk3 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}'
        chunk4 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'

        # Set up the mocks
        mock_completion.side_effect = [non_streaming_response, [chunk1, chunk2, chunk3, chunk4]]  # For non-streaming  # For streaming

        # Test messages
        messages = [{"role": "user", "content": "Hello"}]

        # Get non-streaming response
        with (
            patch.object(provider, "_track_conversation"),
            patch.object(provider, "_get_augmented_messages"),
            patch.object(provider, "_prepare_response", return_value=non_streaming_response),
        ):
            non_streaming_result = provider.completion("test-model", messages)

        # Get streaming response
        with (
            patch.object(provider, "_track_conversation"),
            patch.object(provider, "_get_augmented_messages"),
            patch.object(provider, "_create_memory_if_needed"),
        ):
            streaming_chunks = list(provider.streaming("test-model", messages))

        # Extract content from non-streaming response
        non_streaming_content = non_streaming_result["choices"][0]["message"]["content"]

        # Extract content from streaming response
        streaming_content = ""
        for chunk in streaming_chunks:
            chunk_data = json.loads(chunk)
            if "choices" in chunk_data and chunk_data["choices"][0].get("delta", {}).get("content"):
                streaming_content += chunk_data["choices"][0]["delta"]["content"]

        # Verify the content is the same
        assert streaming_content == non_streaming_content
        assert streaming_content == "Hello world"

    def test_streaming_error_handling(self, client):
        """Test error handling in streaming responses."""
        # Mock an error in the streaming provider
        mock_provider.set_error(Exception("Test streaming error"))

        # Make the request
        request_data = {"model": "test-model", "messages": [{"role": "user", "content": "Hello"}], "stream": True}
        response = client.post("/v1/chat/completions", json=request_data)

        # Check the response
        assert response.status_code == 200

        # Collect the streaming response
        chunks = []
        for chunk in response.iter_lines():
            if chunk:
                chunks.append(chunk)

        # Check that we got an error message and [DONE]
        assert len(chunks) == 2
        error_chunk = json.loads(chunks[0].replace("data: ", ""))
        assert "error" in error_chunk
        assert "message" in error_chunk["error"]
        assert "Test streaming error" in error_chunk["error"]["message"]
        assert chunks[1] == "data: [DONE]"

    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._create_memory_if_needed")
    @patch("litellm.completion")
    def test_memory_creation_after_streaming(self, mock_completion, mock_create_memory, provider):
        """Test that memories are created after streaming responses."""
        # Mock streaming response chunks
        chunk1 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}'
        chunk2 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}'

        # Set up the mock
        mock_completion.return_value = [chunk1, chunk2]

        # Test messages
        messages = [{"role": "user", "content": "Hello"}]

        # Get streaming response
        with patch.object(provider, "_track_conversation"), patch.object(provider, "_get_augmented_messages"):
            list(provider.streaming("test-model", messages))

        # Verify memory creation was attempted
        mock_create_memory.assert_called_once_with(messages)
