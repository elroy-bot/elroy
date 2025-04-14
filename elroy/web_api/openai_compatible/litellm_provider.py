from typing import Any, AsyncIterator, Dict, Iterator, List

import litellm
from litellm.llms.base import BaseLLM

from ...core.constants import ASSISTANT, SYSTEM, USER
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...llm.client import _build_completion_kwargs, context_messages_to_dicts
from ...repository.context_messages.data_models import ContextMessage
from ...repository.context_messages.operations import add_context_messages
from ...repository.context_messages.queries import get_context_messages
from ...repository.memories.operations import (
    do_create_memory_from_ctx_msgs,
    formulate_memory,
)
from ...repository.memories.queries import get_relevant_memories_and_goals

logger = get_logger()


class ElroyLiteLLMProvider(BaseLLM):
    """
    Custom LiteLLM provider that integrates with Elroy's memory system.

    This provider augments chat completion requests with relevant memories
    and handles conversation tracking and memory creation.
    """

    def __init__(
        self,
        ctx: ElroyContext,
        enable_memory_creation: bool = True,
        memory_creation_interval: int = 10,
        max_memories_per_request: int = 5,
    ):
        """
        Initialize the Elroy LiteLLM provider.

        Args:
            ctx: The Elroy context
            enable_memory_creation: Whether to create memories from conversations
            memory_creation_interval: How often to create memories (in messages)
            max_memories_per_request: Maximum number of memories to include per request
        """
        self.ctx = ctx
        self.enable_memory_creation = enable_memory_creation
        self.memory_creation_interval = memory_creation_interval
        self.max_memories_per_request = max_memories_per_request

    def _get_augmented_messages(self, messages: List[ContextMessage]) -> List[ContextMessage]:
        """
        Augment the messages with relevant memories.

        Args:
            messages: The original messages from the request

        Returns:
            The augmented messages with relevant memories included
        """
        # Extract the system message if present
        system_message = None
        user_messages = [m for m in messages if m.role == USER]

        if not user_messages:
            return messages

        # Get relevant memories based on the last few user messages
        # Use the last 3 messages or all if fewer
        query_text = " ".join([m.content or "" for m in user_messages[-3:]])
        relevant_items = get_relevant_memories_and_goals(self.ctx, query_text)

        # Limit the number of memories to include
        relevant_items = relevant_items[: self.max_memories_per_request]

        # If no relevant memories found, return original messages
        if not relevant_items:
            return messages

        # Create memory context to insert before user messages
        memory_context = []
        for item in relevant_items:
            memory_text = f"Relevant memory: {item.to_fact()}"
            memory_context.append(ContextMessage(role=SYSTEM, content=memory_text, chat_model=self.ctx.chat_model.name))

        # Construct the augmented messages
        augmented_messages = []

        # Add system message first if it exists
        if system_message:
            augmented_messages.append(system_message)

        # Add memory context
        augmented_messages.extend(memory_context)

        # Add the rest of the messages
        for msg in messages:
            if msg.role != SYSTEM:  # Skip system message as it's already added
                augmented_messages.append(msg)

        return augmented_messages

    def _track_conversation(self, messages: List[ContextMessage]) -> None:
        """
        Track the conversation by storing messages and handling divergence.

        This implements position-based message comparison to handle conversation branches.

        Args:
            messages: The messages from the request
        """
        # Get existing context messages
        existing_messages = list(get_context_messages(self.ctx))
        existing_non_system = [m for m in existing_messages if m.role != SYSTEM]

        # Convert incoming messages to ContextMessage objects
        new_messages = messages

        # Handle divergence by comparing messages at the same position
        divergence_index = None

        # Skip system messages for comparison
        new_non_system = [m for m in new_messages if m.role != SYSTEM]

        # Compare messages at the same position
        for i, (existing, new) in enumerate(zip(existing_non_system, new_non_system)):
            # Simple exact matching for content
            if existing.content != new.content or existing.role != new.role:
                divergence_index = i
                break

        if divergence_index is not None:
            # Divergence detected - discard all subsequent messages
            logger.info(f"Conversation divergence detected at position {divergence_index}")

            # Keep system message and messages up to divergence point
            messages_to_keep = [m for m in existing_messages if m.role == SYSTEM]
            messages_to_keep.extend(existing_non_system[:divergence_index])

            # Add the new divergent message and all following messages
            messages_to_add = new_non_system[divergence_index:]

            # Replace context messages
            add_context_messages(self.ctx, messages_to_add)
        else:
            # No divergence, just add any new messages
            if len(new_non_system) > len(existing_non_system):
                messages_to_add = new_non_system[len(existing_non_system) :]
                add_context_messages(self.ctx, messages_to_add)

    def _create_memory_if_needed(self, messages: List[Any]) -> None:
        """
        Create a memory from the conversation if needed.

        Args:
            messages: The messages from the request
        """

        # TODO
        if not self.enable_memory_creation:
            return

        # Get all context messages
        context_messages = list(get_context_messages(self.ctx))

        # Check if we have enough messages to create a memory
        user_assistant_messages = [m for m in context_messages if m.role in (USER, ASSISTANT)]

        if len(user_assistant_messages) >= self.memory_creation_interval:
            # Create memory asynchronously
            try:
                memory_title, memory_text = formulate_memory(
                    self.ctx,
                    context_messages,
                )
                do_create_memory_from_ctx_msgs(self.ctx, memory_title, memory_text)
                logger.info(f"Created memory: {memory_title}")
            except Exception as e:
                logger.error(f"Error creating memory: {e}")

    def _prepare_response(self, response: Any, model: str) -> Any:
        """
        Prepare the response by adding Elroy-specific metadata.

        Args:
            response: The original response from the LLM
            model: The model name

        Returns:
            The prepared response
        """
        # Create memory after response if needed
        try:
            self._create_memory_if_needed(response.choices[0].message)
        except Exception as e:
            logger.error(f"Error in memory creation: {e}")

        return response

    def to_context_messages(self, messages: List[Dict[str, Any]]) -> List[ContextMessage]:
        ctx_msgs = []
        for msg in messages:
            if type(msg["content"]) == str:
                content = msg["content"].strip()
            elif type(msg["content"]) == list:
                content_text = []
                for m in msg["content"]:
                    if m["type"] == "text":
                        content_text.append(m["text"])
                    else:
                        logger.warning("discarding non-text content of type: " + str(m["type"]))
                content = "\n".join(content_text)
            else:
                raise ValueError(f"Unsupported message content type: {type(msg['content'])}")

            ctx_msgs.append(
                ContextMessage(
                    role=msg["role"],
                    content=content,
                    chat_model=self.ctx.chat_model.name,
                )
            )
        return ctx_msgs

    def completion(self, model: str, raw_messages: List[Dict[str, Any]], **kwargs) -> Any:
        """
        Generate a non-streaming completion.

        Args:
            model: The model to use
            messages: The messages for the completion
            **kwargs: Additional arguments for the completion

        Returns:
            The completion response
        """
        # Track conversation
        messages = self.to_context_messages(raw_messages)
        self._track_conversation(messages)

        # Augment messages with memories
        augmented_messages: List[Dict] = context_messages_to_dicts(self._get_augmented_messages(messages))

        # Build completion kwargs
        completion_kwargs = _build_completion_kwargs(
            model=self.ctx.chat_model,
            messages=augmented_messages,
            stream=False,
            tool_choice=kwargs.get("tool_choice"),
            tools=kwargs.get("tools"),
        )

        # Add any additional kwargs
        for key, value in kwargs.items():
            if key not in completion_kwargs and key not in ["model", "messages"]:
                completion_kwargs[key] = value

        # Call the underlying LLM
        response = litellm.completion(**completion_kwargs)

        # Prepare and return the response
        return self._prepare_response(response, model)

    def streaming(self, model: str, raw_messages: List[Dict[str, Any]], **kwargs) -> Iterator[Any]:
        """
        Generate a streaming completion.

        Args:
            model: The model to use
            messages: The messages for the completion
            **kwargs: Additional arguments for the completion

        Returns:
            An iterator of streaming chunks
        """
        # Track conversation
        messages = self.to_context_messages(raw_messages)
        self._track_conversation(messages)

        # Augment messages with memories
        augmented_messages = context_messages_to_dicts(self._get_augmented_messages(messages))

        # Build completion kwargs
        completion_kwargs = _build_completion_kwargs(
            model=self.ctx.chat_model,
            messages=augmented_messages,
            stream=True,
            tool_choice=kwargs.get("tool_choice"),
            tools=kwargs.get("tools"),
        )

        # Add any additional kwargs
        for key, value in kwargs.items():
            if key not in completion_kwargs and key not in ["model", "messages"]:
                completion_kwargs[key] = value

        # Call the underlying LLM
        response_iter = litellm.completion(**completion_kwargs)

        # Yield each chunk
        last_chunk = None
        for chunk in response_iter:
            last_chunk = chunk
            yield chunk

        # Create memory after response if needed
        if last_chunk:
            try:
                self._create_memory_if_needed(messages)
            except Exception as e:
                logger.error(f"Error in memory creation: {e}")

    async def acompletion(self, model: str, raw_messages: List[Dict[str, Any]], **kwargs) -> Any:
        """
        Generate an async non-streaming completion.

        Args:
            model: The model to use
            messages: The messages for the completion
            **kwargs: Additional arguments for the completion

        Returns:
            The completion response
        """
        # Track conversation
        messages = self.to_context_messages(raw_messages)
        self._track_conversation(messages)

        # Augment messages with memories
        augmented_messages = context_messages_to_dicts(self._get_augmented_messages(messages))

        # Build completion kwargs
        completion_kwargs = _build_completion_kwargs(
            model=self.ctx.chat_model,
            messages=augmented_messages,
            stream=False,
            tool_choice=kwargs.get("tool_choice"),
            tools=kwargs.get("tools"),
        )

        # Add any additional kwargs
        for key, value in kwargs.items():
            if key not in completion_kwargs and key not in ["model", "messages"]:
                completion_kwargs[key] = value

        # Call the underlying LLM
        response = await litellm.acompletion(**completion_kwargs)

        # Prepare and return the response
        return self._prepare_response(response, model)

    async def astreaming(self, model: str, raw_messages: List[Dict[str, Any]], **kwargs) -> AsyncIterator[Any]:
        """
        Generate an async streaming completion.

        Args:
            model: The model to use
            messages: The messages for the completion
            **kwargs: Additional arguments for the completion

        Returns:
            An async iterator of streaming chunks
        """
        # Track conversation

        messages = self.to_context_messages(raw_messages)
        self._track_conversation(messages)

        # Augment messages with memories
        augmented_messages = context_messages_to_dicts(self._get_augmented_messages(messages))

        # Build completion kwargs
        completion_kwargs = _build_completion_kwargs(
            model=self.ctx.chat_model,
            messages=augmented_messages,
            stream=True,
            tool_choice=kwargs.get("tool_choice"),
            tools=kwargs.get("tools"),
        )

        # Add any additional kwargs
        for key, value in kwargs.items():
            if key not in completion_kwargs and key not in ["model", "messages"]:
                completion_kwargs[key] = value

        # Call the underlying LLM
        response_stream = await litellm.acompletion(**completion_kwargs)

        # Yield each chunk
        last_chunk = None
        for chunk in response_stream:
            last_chunk = chunk
            yield chunk

        # Create memory after response if needed
        if last_chunk:
            try:
                self._create_memory_if_needed(messages)
            except Exception as e:
                logger.error(f"Error in memory creation: {e}")
