import os
import time
from typing import Any, Dict, Generator, List, Optional, Union

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
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


class ChatCompletionMessage(BaseModel):
    role: str
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatCompletionMessage]
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


def get_db_session() -> DbSession:
    """Get a database session."""
    # Get database URL from environment or use a default
    database_url = os.environ.get("DATABASE_URL", "sqlite:///elroy.db")

    # Get a database manager
    db_manager = get_db_manager(database_url)

    # Open a session
    return db_manager.open_session().__enter__()


def get_elroy_context(db: DbSession = Depends(get_db_session)) -> Generator[ElroyContext, Any, None]:
    """Get an Elroy context."""
    # Create a basic ElroyContext with default parameters
    params = get_resolved_params()
    ctx = ElroyContext(use_background_threads=False, **params)
    with dbsession(ctx):
        yield ctx
    #     database_url=os.environ.get("DATABASE_URL", "sqlite:///elroy.db"),
    #     show_internal_thought=True,
    #     system_message_color="blue",
    #     assistant_color="green",
    #     user_input_color="yellow",
    #     warning_color="red",
    #     internal_thought_color="magenta",
    #     user_token="openai-api-user",
    #     chat_model=os.environ.get("CHAT_MODEL", "gpt-3.5-turbo"),
    #     embedding_model="text-embedding-ada-002",
    #     embedding_model_size=1536,
    #     max_assistant_loops=10,
    #     max_tokens=4000,
    #     max_context_age_minutes=60,
    #     min_convo_age_for_greeting_minutes=5,
    #     memory_cluster_similarity_threshold=0.7,
    #     max_memory_cluster_size=10,
    #     min_memory_cluster_size=2,
    #     memories_between_consolidation=5,
    #     messages_between_memory=10,
    #     l2_memory_relevance_distance_threshold=RELEVANCE_THRESHOLD,
    #     debug=False,
    #     default_assistant_name="Elroy",
    #     use_background_threads=True,
    #     max_ingested_doc_lines=1000,
    #     reflect=True,
    # )

    # Set the database session
    # ctx.set_db_session(db)


def get_litellm_provider(ctx: ElroyContext = Depends(get_elroy_context)) -> ElroyLiteLLMProvider:
    """Get an ElroyLiteLLMProvider instance."""
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
    request: ChatCompletionRequest,
    provider: ElroyLiteLLMProvider = Depends(get_litellm_provider),
):
    """
    OpenAI-compatible chat completions endpoint.

    This endpoint accepts requests in the same format as OpenAI's chat completions API
    and returns responses in the same format, but augmented with memories from Elroy.
    """
    try:
        # Convert Pydantic model to dict
        messages = [message.dict(exclude_none=True) for message in request.messages]

        # Extract parameters
        params = request.dict(exclude={"messages", "model", "stream"})

        # Handle streaming
        if request.stream:
            return StreamingResponse(
                stream_chat_completion(provider, request.model, messages, params),
                media_type="text/event-stream",
            )

        # Handle non-streaming
        response = provider.completion(request.model, messages, **params)

        # Return the response
        return response
    except Exception as e:
        logger.error(f"Error in chat completions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"message": str(e), "type": "internal_server_error"}},
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
