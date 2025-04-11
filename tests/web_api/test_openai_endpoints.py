import time
from typing import Any, Dict, List, Optional, Union

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

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
                streaming_response = mock_provider.streaming(request.model, request.messages)
                if streaming_response:
                    for chunk in streaming_response:
                        yield chunk
                else:
                    yield "data: {}\n\n"
                    yield "data: [DONE]\n\n"

            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream",
            )
        else:
            # Return non-streaming response
            return mock_provider.completion(request.model, request.messages)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": str(e), "type": "internal_server_error"}},
        )


# Test client
@pytest.fixture
def client():
    return TestClient(app)


# Tests
class TestOpenAIEndpoints:
    def test_root_endpoint(self, client):
        """Test the root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "description" in data

    def test_health_endpoint(self, client):
        """Test the health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_chat_completions_non_streaming(self, client):
        """Test the chat completions endpoint with non-streaming response."""
        # Set up the mock response
        mock_response = {
            "id": "test-id",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "test-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello, how can I help you?"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }
        mock_provider.set_completion_response(mock_response)
        mock_provider.set_error(None)

        # Make the request
        request_data = {"model": "test-model", "messages": [{"role": "user", "content": "Hello"}], "temperature": 0.7}
        response = client.post("/v1/chat/completions", json=request_data)

        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert data == mock_response

    def test_chat_completions_streaming(self, client):
        """Test the chat completions endpoint with streaming response."""
        # Set up the mock streaming response
        mock_provider.set_streaming_response(["data: chunk1\n\n", "data: chunk2\n\n", "data: [DONE]\n\n"])
        mock_provider.set_error(None)

        # Make the request
        request_data = {"model": "test-model", "messages": [{"role": "user", "content": "Hello"}], "temperature": 0.7, "stream": True}
        response = client.post("/v1/chat/completions", json=request_data)

        # Check the response
        assert response.status_code == 200

        # Get the content as text
        content = response.content.decode("utf-8")

        # Check that we got a streaming response
        assert "data: chunk1" in content
        assert "data: chunk2" in content
        assert "data: [DONE]" in content

    def test_chat_completions_error(self, client):
        """Test error handling in the chat completions endpoint."""
        # Set up the mock error
        mock_provider.set_error(Exception("Test error"))

        # Make the request
        request_data = {"model": "test-model", "messages": [{"role": "user", "content": "Hello"}]}
        response = client.post("/v1/chat/completions", json=request_data)

        # Check the response
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert "message" in data["detail"]["error"]
        assert "Test error" in data["detail"]["error"]["message"]

    def test_chat_completions_invalid_request(self, client):
        """Test the chat completions endpoint with an invalid request."""
        # Make an invalid request (missing required fields)
        request_data = {"messages": [{"role": "user", "content": "Hello"}]}

        response = client.post("/v1/chat/completions", json=request_data)

        # Check the response
        assert response.status_code == 422  # Validation error
