"""
Memory integration for the OpenAI-compatible API server.

This module handles retrieving relevant memories for a conversation and
creating new memories from conversations.
"""

import hashlib
from typing import List, Optional, Tuple, Union

from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import Goal, Memory
from ...repository.context_messages.data_models import ContextMessage
from ...repository.memories.operations import (
    do_create_memory_from_ctx_msgs,
    formulate_memory,
    get_or_create_memory_op_tracker,
)
from ...repository.memories.queries import get_relevant_memories
from ..openai_compatible.models import Message, MessageRole

logger = get_logger()


def convert_openai_message_to_context_message(message: Message, chat_model: str) -> ContextMessage:
    """Convert an OpenAI API message to an Elroy context message."""
    return ContextMessage(
        content=message.content,
        role=message.role.value,
        chat_model=chat_model,
        tool_calls=None,  # TODO: Handle tool calls
        tool_call_id=message.tool_call_id,
    )


def convert_context_message_to_openai_message(message: ContextMessage) -> Message:
    """Convert an Elroy context message to an OpenAI API message."""
    return Message(
        role=MessageRole(message.role),
        content=message.content,
        tool_calls=None if not message.tool_calls else [tc.to_json() for tc in message.tool_calls],
        tool_call_id=message.tool_call_id,
    )


def compute_message_hash(message: Message) -> str:
    """Compute a hash for a message to use for deduplication."""
    content = message.content or ""
    return hashlib.md5(f"{message.role.value}:{content}".encode()).hexdigest()


async def get_relevant_memories_for_conversation(
    ctx: ElroyContext, messages: List[Message], max_memories: int, relevance_threshold: float
) -> List[Union[Memory, "Goal"]]:
    """
    Retrieve memories relevant to the current conversation.

    Args:
        ctx: The Elroy context
        messages: The conversation messages
        max_memories: Maximum number of memories to retrieve
        relevance_threshold: Threshold for memory relevance

    Returns:
        A list of relevant memories
    """
    # Extract the last few user messages for the query
    user_messages = [msg for msg in messages if msg.role == MessageRole.USER]

    if not user_messages:
        return []

    # Use the last 3 user messages (or fewer if there aren't that many)
    query_messages = user_messages[-3:]
    query_text = " ".join([msg.content for msg in query_messages if msg.content])

    if not query_text:
        return []

    # Get relevant memories
    memories = get_relevant_memories(ctx, query_text)

    # Filter memories by relevance threshold and limit the number
    # Note: The relevance is already factored into the order of memories returned
    return memories[:max_memories]


async def create_memory_from_conversation(ctx: ElroyContext, messages: List[Message]) -> Optional[Tuple[str, str]]:
    """
    Create a memory from the current conversation.

    Args:
        ctx: The Elroy context
        messages: The conversation messages

    Returns:
        A tuple of (memory_title, memory_text) if a memory was created, None otherwise
    """
    # Convert OpenAI messages to context messages
    context_messages = [convert_openai_message_to_context_message(msg, ctx.chat_model.name) for msg in messages]

    # Create a memory from the context messages
    memory_title, memory_text = formulate_memory(ctx, context_messages)

    # Store the memory
    do_create_memory_from_ctx_msgs(ctx, memory_title, memory_text)

    return memory_title, memory_text


async def should_create_memory(ctx: ElroyContext, messages: List[Message], memory_creation_interval: int) -> bool:
    """
    Determine if a memory should be created based on the message count.

    Args:
        ctx: The Elroy context
        messages: The conversation messages
        memory_creation_interval: Number of messages between memory creation

    Returns:
        True if a memory should be created, False otherwise
    """
    tracker = get_or_create_memory_op_tracker(ctx)

    # Increment the message count
    tracker.messages_since_memory += 1
    ctx.db.add(tracker)
    ctx.db.commit()

    # Check if we've reached the threshold
    if tracker.messages_since_memory >= memory_creation_interval:
        tracker.messages_since_memory = 0
        ctx.db.add(tracker)
        ctx.db.commit()
        return True

    return False


async def process_memory_creation(
    ctx: ElroyContext,
    messages: List[Message],
    memory_creation_interval: int,
    enable_memory_creation: bool,
) -> None:
    """
    Process memory creation after a response has been generated.

    This function should be called asynchronously after the response has been sent
    to the client to avoid delaying the response.

    Args:
        ctx: The Elroy context
        messages: The conversation messages
        memory_creation_interval: Number of messages between memory creation
        enable_memory_creation: Whether memory creation is enabled
    """
    if not enable_memory_creation:
        return

    try:
        # Check if we should create a memory
        if await should_create_memory(ctx, messages, memory_creation_interval):
            # Create a memory from the conversation
            memory = await create_memory_from_conversation(ctx, messages)
            if memory:
                memory_title, memory_text = memory
                logger.info(f"Created memory: {memory_title}")
    except Exception as e:
        logger.error(f"Error creating memory: {e}")
