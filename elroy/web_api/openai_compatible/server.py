"""
OpenAI-compatible API server for Elroy.

This module provides a FastAPI server that implements an OpenAI-compatible API
endpoint for chat completions, augmented with Elroy's memory capabilities.
"""

import asyncio
import json
import time
import uuid
from typing import AsyncGenerator, Dict, List, Union

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader

from ...cli.options import get_resolved_params
from ...config.llm import ChatModel
from ...core.constants import Provider
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...llm.client import generate_chat_completion_message
from ...llm.utils import count_tokens
from ...repository.context_messages.data_models import ContextMessage
from ...repository.user.queries import do_get_user_preferred_name, get_assistant_name
from ..openai_compatible.config import get_config
from ..openai_compatible.conversation import ConversationTracker
from ..openai_compatible.memory import (
    convert_context_message_to_openai_message,
    get_relevant_memories_for_conversation,
    process_memory_creation,
)
from ..openai_compatible.models import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatCompletionResponseMessage,
    DeltaMessage,
    MessageRole,
    UsageInfo,
)

logger = get_logger()
app = FastAPI(title="Elroy OpenAI-Compatible API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key security
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


def get_context() -> ElroyContext:
    """Get the Elroy context for the current request."""
    # For now, we'll use a fixed user token
    # In a real implementation, this would be based on authentication

    # Create a minimal ElroyContext with default values
    ctx = ElroyContext(**get_resolved_params(use_background_threads=True))
    # database_url="sqlite:///elroy.db",  # Use default database
    # show_internal_thought=False,
    # system_message_color="blue",
    # assistant_color="green",
    # user_input_color="yellow",
    # warning_color="red",
    # internal_thought_color="magenta",
    # user_token=user_token,
    # embedding_model="text-embedding-ada-002",
    # embedding_model_size=1536,
    # max_assistant_loops=10,
    # max_tokens=4000,
    # max_context_age_minutes=60,
    # min_convo_age_for_greeting_minutes=5,
    # memory_cluster_similarity_threshold=0.7,
    # max_memory_cluster_size=10,
    # min_memory_cluster_size=2,
    # memories_between_consolidation=10,
    # messages_between_memory=10,
    # l2_memory_relevance_distance_threshold=0.7,
    # debug=False,
    # default_assistant_name="Elroy",
    # use_background_threads=True,
    # max_ingested_doc_lines=1000,
    # reflect=True,
    # )

    # Open a database session
    db_manager = ctx.db_manager
    with db_manager.open_session() as db_session:
        ctx.set_db_session(db_session)
        return ctx


async def verify_api_key(api_key_header: str = Depends(api_key_header)) -> bool:
    """Verify the API key if authentication is enabled."""
    config = get_config()

    if not config.enable_auth:
        return True

    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    # Extract the key from the header (format: "Bearer <api_key>")
    key = api_key_header.replace("Bearer ", "") if api_key_header.startswith("Bearer ") else api_key_header

    if key not in config.api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return True


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    ctx: ElroyContext = Depends(get_context),
    _: bool = Depends(verify_api_key),
) -> Union[ChatCompletionResponse, StreamingResponse]:
    """
    OpenAI-compatible chat completions endpoint.

    This endpoint accepts requests in the same format as OpenAI's chat completions
    API and returns responses in the same format, but augmented with Elroy's
    memory capabilities.
    """
    config = get_config()

    # Get the chat model
    chat_model = ChatModel(
        name=request.model,
        enable_caching=True,
        api_key=None,
        provider=Provider.OPENAI,
        inline_tool_calls=False,
        ensure_alternating_roles=True,
    )
    ctx.chat_model = chat_model

    # Track the conversation
    conversation_tracker = ConversationTracker(ctx)
    context_messages, diverged = conversation_tracker.compare_and_update_conversation(request.messages)

    # Get relevant memories
    memories = await get_relevant_memories_for_conversation(
        ctx,
        request.messages,
        config.max_memories_per_request,
        config.relevance_threshold,
    )

    # Add memories to the context
    memory_context_messages = []
    if memories:
        do_get_user_preferred_name(ctx.db.session, ctx.user_id)
        get_assistant_name(ctx)

        # Helper function to safely get memory content
        def get_memory_content(memory):
            """Get the content of a memory, handling both Memory and Goal objects."""
            if hasattr(memory, "to_fact"):
                return memory.to_fact()
            elif hasattr(memory, "text"):
                return memory.text
            else:
                return str(memory)

        for memory in memories:
            memory_content = get_memory_content(memory)
            memory_text = f"Memory: {memory.name}\n{memory_content}"
            memory_context_messages.append(
                ContextMessage(
                    role="system",
                    content=memory_text,
                    chat_model=chat_model.name,
                )
            )

    # Combine system messages, memories, and conversation messages
    system_messages = [msg for msg in context_messages if msg.role == "system"]
    non_system_messages = [msg for msg in context_messages if msg.role != "system"]

    # Ensure we have at least one system message
    if not system_messages:
        system_messages = [
            ContextMessage(
                role="system",
                content="You are a helpful assistant.",
                chat_model=chat_model.name,
            )
        ]

    # Combine all messages
    augmented_context_messages = system_messages + memory_context_messages + non_system_messages

    # Generate the response
    if request.stream:
        return StreamingResponse(
            stream_chat_completion(
                ctx,
                request,
                augmented_context_messages,
                config.enable_memory_creation,
                config.memory_creation_interval,
            ),
            media_type="text/event-stream",
        )
    else:
        return await generate_chat_completion(
            ctx,
            request,
            augmented_context_messages,
            config.enable_memory_creation,
            config.memory_creation_interval,
        )


async def generate_chat_completion(
    ctx: ElroyContext,
    request: ChatCompletionRequest,
    context_messages: List[ContextMessage],
    enable_memory_creation: bool,
    memory_creation_interval: int,
) -> ChatCompletionResponse:
    """
    Generate a chat completion response.

    Args:
        ctx: The Elroy context
        request: The chat completion request
        context_messages: The context messages to use for the response
        enable_memory_creation: Whether to enable memory creation
        memory_creation_interval: The interval for memory creation

    Returns:
        A chat completion response
    """
    # Generate the response
    stream_parser = generate_chat_completion_message(
        ctx.chat_model,
        context_messages,
        [],  # No tools for now
        enable_tools=False,
    )

    # Collect the response
    response_text = ""
    for chunk in stream_parser.process_stream():
        if hasattr(chunk, "content"):
            response_text += chunk.content

    # Create the response
    response = ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        model=request.model,
        choices=[
            ChatCompletionResponseChoice(
                index=0,
                message=ChatCompletionResponseMessage(
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                ),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(
            prompt_tokens=count_tokens(ctx.chat_model.name, context_messages),
            completion_tokens=count_tokens(
                ctx.chat_model.name,
                ContextMessage(
                    role="assistant",
                    content=response_text,
                    chat_model=ctx.chat_model.name,
                ),
            ),
            total_tokens=count_tokens(ctx.chat_model.name, context_messages)
            + count_tokens(
                ctx.chat_model.name,
                ContextMessage(
                    role="assistant",
                    content=response_text,
                    chat_model=ctx.chat_model.name,
                ),
            ),
        ),
    )

    # Process memory creation asynchronously
    if enable_memory_creation:
        asyncio.create_task(
            process_memory_creation(
                ctx,
                request.messages
                + [
                    convert_context_message_to_openai_message(
                        ContextMessage(
                            role="assistant",
                            content=response_text,
                            chat_model=ctx.chat_model.name,
                        )
                    )
                ],
                memory_creation_interval,
                enable_memory_creation,
            )
        )

    return response


async def stream_chat_completion(
    ctx: ElroyContext,
    request: ChatCompletionRequest,
    context_messages: List[ContextMessage],
    enable_memory_creation: bool,
    memory_creation_interval: int,
) -> AsyncGenerator[str, None]:
    """
    Stream a chat completion response.

    Args:
        ctx: The Elroy context
        request: The chat completion request
        context_messages: The context messages to use for the response
        enable_memory_creation: Whether to enable memory creation
        memory_creation_interval: The interval for memory creation

    Yields:
        Chunks of the streaming response
    """
    # Generate the response
    stream_parser = generate_chat_completion_message(
        ctx.chat_model,
        context_messages,
        [],  # No tools for now
        enable_tools=False,
    )

    # Create a unique ID for this completion
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created_time = int(time.time())

    # Send the first chunk with the role
    first_chunk = ChatCompletionChunk(
        id=completion_id,
        model=request.model,
        created=created_time,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=DeltaMessage(role=MessageRole.ASSISTANT),
                finish_reason=None,
            )
        ],
    )
    yield f"data: {json.dumps(first_chunk.dict())}\n\n"

    # Stream the response
    response_text = ""
    for chunk in stream_parser.process_stream():
        if hasattr(chunk, "content"):
            response_text += chunk.content

            # Create a chunk with the content
            content_chunk = ChatCompletionChunk(
                id=completion_id,
                model=request.model,
                created=created_time,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=DeltaMessage(content=chunk.content),
                        finish_reason=None,
                    )
                ],
            )
            yield f"data: {json.dumps(content_chunk.dict())}\n\n"

    # Send the final chunk
    final_chunk = ChatCompletionChunk(
        id=completion_id,
        model=request.model,
        created=created_time,
        choices=[
            ChatCompletionChunkChoice(
                index=0,
                delta=DeltaMessage(),
                finish_reason="stop",
            )
        ],
    )
    yield f"data: {json.dumps(final_chunk.dict())}\n\n"

    # Send the [DONE] message
    yield "data: [DONE]\n\n"

    # Process memory creation asynchronously
    if enable_memory_creation:
        asyncio.create_task(
            process_memory_creation(
                ctx,
                request.messages
                + [
                    convert_context_message_to_openai_message(
                        ContextMessage(
                            role="assistant",
                            content=response_text,
                            chat_model=ctx.chat_model.name,
                        )
                    )
                ],
                memory_creation_interval,
                enable_memory_creation,
            )
        )


@app.get("/v1/models")
async def list_models(_: bool = Depends(verify_api_key)) -> Dict:
    """
    List available models.

    This is a simple implementation that returns a fixed list of models.
    In a real implementation, this would query the available models from the
    configuration.
    """
    return {
        "object": "list",
        "data": [
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
        ],
    }


@app.get("/")
async def root() -> Dict:
    """Root endpoint that returns basic information about the API."""
    return {
        "message": "Elroy OpenAI-Compatible API",
        "version": "0.1.0",
        "documentation": "/docs",
    }


def run_server() -> None:
    """Run the server."""
    config = get_config()
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    run_server()
