import logging
import os
import time
from typing import Any, Dict, Generator, List, Optional, Union

from fastapi.exceptions import RequestValidationError
from litellm import AllMessageValues
import uvicorn
from fastapi import Body, Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ...cli.options import get_resolved_params
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...core.session import dbsession
from ...db.db_manager import get_db_manager
from ...db.db_session import DbSession
from .litellm_provider import ElroyLiteLLMProvider

logger = get_logger()

app = FastAPI(
    title="Elroy OpenAI-Compatible API",
    description="An OpenAI-compatible API that augments chat completion requests with memories",
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

# Configuration from environment variables
PORT = int(os.environ.get("PORT", "8000"))
HOST = os.environ.get("HOST", "127.0.0.1")
ENABLE_AUTH = os.environ.get("ENABLE_AUTH", "false").lower() == "true"
API_KEYS = os.environ.get("API_KEYS", "").split(",") if ENABLE_AUTH else []
ENABLE_MEMORY_CREATION = os.environ.get("ENABLE_MEMORY_CREATION", "true").lower() == "true"
MEMORY_CREATION_INTERVAL = int(os.environ.get("MEMORY_CREATION_INTERVAL", "10"))
MAX_MEMORIES_PER_REQUEST = int(os.environ.get("MAX_MEMORIES_PER_REQUEST", "5"))
RELEVANCE_THRESHOLD = float(os.environ.get("RELEVANCE_THRESHOLD", "0.7"))


class ContentBlock(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[Dict[str, str]] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[AllMessageValues]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    # presence_penalty: Optional[float] = 0.0
    # frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None


def get_elroy_context() -> Generator[ElroyContext, Any, None]:
    """Get an Elroy context."""
    # Create a basic ElroyContext with default parameters
    params = get_resolved_params()
    ctx = ElroyContext(use_background_threads=False, **params)
    with dbsession(ctx):
        yield ctx


def get_litellm_provider(ctx: ElroyContext = Depends(get_elroy_context)) -> ElroyLiteLLMProvider:
    """Get an ElroyLiteLLMProvider instance."""
    params = get_resolved_params()
    ctx = ElroyContext(use_background_threads=False, **params)
    return ElroyLiteLLMProvider(
        ctx=ctx,
        enable_memory_creation=ENABLE_MEMORY_CREATION,
        memory_creation_interval=MEMORY_CREATION_INTERVAL,
        max_memories_per_request=MAX_MEMORIES_PER_REQUEST,
    )

def verify_api_key(request: Request) -> bool:
    """Verify the API key if authentication is enabled."""
    if not ENABLE_AUTH:
        return True

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return False

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False

    api_key = parts[1]
    return api_key in API_KEYS


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Middleware to handle authentication."""
    if request.url.path.startswith("/v1/") and not verify_api_key(request):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": {"message": "Invalid API key", "type": "invalid_request_error"}},
        )

    return await call_next(request)


@app.post("/v1/chat/completions")
async def chat_completions(
    request_data: ChatCompletionRequest = Body(...),
    provider: ElroyLiteLLMProvider = Depends(get_litellm_provider),
):
    """
    OpenAI-compatible chat completions endpoint with enhanced error handling.

    This endpoint accepts requests in the same format as OpenAI's chat completions API
    and returns responses in the same format, but augmented with memories from Elroy.
    """
    with dbsession(provider.ctx):
        try:
            # Convert Pydantic model to dict
            messages = [dict(m) for m in request_data.messages]

            # Extract parameters
            params = request_data.model_dump(exclude={"messages", "model", "stream"})

            # Handle streaming
            if request_data.stream:
                return StreamingResponse(
                    stream_chat_completion(provider, request_data.model, messages, params),
                    media_type="text/event-stream",
                )

            # Handle non-streaming
            response = provider.completion(request_data.model, messages, **params)

            # Return the response
            return response
        except Exception as e:
            logger.error(f"Error in chat completions: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": {"message": str(e), "type": "internal_server_error", "param": None, "code": "internal_error"}},
            )


async def stream_chat_completion(provider, model, messages, params):
    """
    Stream a chat completion response.

    Args:
        provider: The ElroyLiteLLMProvider instance
        model: The model to use
        messages: The messages for the completion
        params: Additional parameters for the completion

    Yields:
        Streaming response chunks in the SSE format
    """
    with dbsession(provider.ctx):
        try:
            for chunk in provider.streaming(model, messages, **params):
                # Convert chunk to JSON and yield in SSE format
                yield f"data: {chunk}\n\n"

            # End the stream
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            error_json = {"error": {"message": str(e), "type": "internal_server_error"}}
            yield f"data: {error_json}\n\n"
            yield "data: [DONE]\n\n"


@app.get("/v1/models")
async def list_models():
    """
    OpenAI-compatible models endpoint.

    Returns a list of available models in OpenAI format.
    """
    # You can customize this list based on your available models
    models = [
        {
            "id": "gpt-3.5-turbo",
            "object": "model",
            "created": int(time.time()),
            "owned_by": "elroy",
        },
        {
            "id": "gpt-4",
            "object": "model",
            "created": int(time.time()),
            "owned_by": "elroy",
        },
        # Add other models you support
    ]

    return {"object": "list", "data": models}


@app.get("/")
async def root():
    """Root endpoint that returns basic information about the API."""
    return {
        "name": "Elroy OpenAI-Compatible API",
        "version": "0.1.0",
        "description": "An OpenAI-compatible API that augments chat completion requests with memories",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": time.time()}


def run_server():
    """Run the server."""
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    run_server()
