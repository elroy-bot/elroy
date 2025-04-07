"""
LiteLLM custom provider for Elroy's OpenAI-compatible API server.

This module implements a custom LiteLLM provider that integrates with Elroy's
memory-augmented chat completion capabilities.
"""

import asyncio
import time
import uuid
from typing import Any, AsyncIterator, Callable, Dict, Iterator, Optional, Union

import httpx
from litellm.llms.base import BaseLLM
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler

from ...cli.options import get_resolved_params
from ...config.llm import ChatModel
from ...core.constants import Provider
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...llm.client import generate_chat_completion_message
from ...llm.utils import count_tokens
from ...repository.context_messages.data_models import ContextMessage
from ..openai_compatible.config import get_config
from ..openai_compatible.conversation import ConversationTracker
from ..openai_compatible.memory import (
    convert_openai_message_to_context_message,
    get_relevant_memories_for_conversation,
    process_memory_creation,
)

logger = get_logger()


class ElroyLLMError(Exception):
    """Exception raised for errors in the ElroyLLM provider."""

    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class ElroyLLM(BaseLLM):
    """
    Custom LiteLLM provider for Elroy's OpenAI-compatible API server.

    This provider integrates with Elroy's memory system to augment chat completions
    with relevant memories.
    """

    def __init__(self) -> None:
        super().__init__()

    def _get_memory_content(self, memory):
        """Get the content of a memory, handling both Memory and Goal objects."""
        if hasattr(memory, "to_fact"):
            return memory.to_fact()
        elif hasattr(memory, "text"):
            return memory.text
        else:
            return str(memory)

    def completion(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: Any,
        print_verbose: Callable,
        encoding,
        api_key,
        logging_obj,
        optional_params: dict,
        acompletion=None,
        litellm_params=None,
        logger_fn=None,
        headers={},
        timeout: Optional[Union[float, httpx.Timeout]] = None,
        client: Optional[HTTPHandler] = None,
    ) -> Any:
        """
        Handle non-streaming completion requests for Elroy.

        Args:
            model: The model to use for completion
            messages: The messages to process
            api_base: The API base URL
            custom_prompt_dict: Custom prompt dictionary
            model_response: The model response object to populate
            print_verbose: Function for verbose printing
            encoding: The encoding to use
            api_key: The API key
            logging_obj: Logging object
            optional_params: Optional parameters
            acompletion: Async completion function
            litellm_params: LiteLLM parameters
            logger_fn: Logger function
            headers: HTTP headers
            timeout: Request timeout
            client: HTTP client

        Returns:
            A populated ModelResponse object
        """
        try:
            # Create Elroy context
            ctx = ElroyContext(**get_resolved_params(use_background_threads=True))

            # Set up chat model
            chat_model = ChatModel(
                name=model,
                enable_caching=True,
                api_key=api_key,
                provider=Provider.OPENAI,
                inline_tool_calls=False,
                ensure_alternating_roles=True,
            )
            ctx.chat_model = chat_model

            # Get config
            config = get_config()

            # Track the conversation
            ConversationTracker(ctx)

            # Convert messages to Elroy format
            elroy_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    # Convert dict to proper format expected by convert_openai_message_to_context_message
                    from ..openai_compatible.models import Message, MessageRole

                    role = MessageRole(msg["role"])
                    content = msg.get("content")
                    name = msg.get("name")
                    tool_calls = msg.get("tool_calls")
                    tool_call_id = msg.get("tool_call_id")
                    openai_msg = Message(role=role, content=content, name=name, tool_calls=tool_calls, tool_call_id=tool_call_id)
                    elroy_messages.append(convert_openai_message_to_context_message(openai_msg, chat_model.name))
                else:
                    elroy_messages.append(convert_openai_message_to_context_message(msg, chat_model.name))

            # Get relevant memories
            memories = asyncio.run(
                get_relevant_memories_for_conversation(
                    ctx,
                    messages,
                    config.max_memories_per_request,
                    config.relevance_threshold,
                )
            )

            # Add memories to context
            memory_context_messages = []
            if memories:
                for memory in memories:
                    memory_content = self._get_memory_content(memory)
                    memory_text = f"Memory: {memory.name}\n{memory_content}"
                    memory_context_messages.append(
                        ContextMessage(
                            role="system",
                            content=memory_text,
                            chat_model=chat_model.name,
                        )
                    )

            # Combine system messages, memories, and conversation messages
            system_messages = [msg for msg in elroy_messages if msg.role == "system"]
            non_system_messages = [msg for msg in elroy_messages if msg.role != "system"]

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
            stream_parser = generate_chat_completion_message(
                ctx.chat_model,
                augmented_context_messages,
                [],  # No tools for now
                enable_tools=False,
            )

            # Collect the response
            response_text = ""
            for chunk in stream_parser.process_stream():
                if hasattr(chunk, "content"):
                    response_text += chunk.content

            # Process memory creation asynchronously if enabled
            if config.enable_memory_creation:
                asyncio.create_task(
                    process_memory_creation(
                        ctx,
                        messages + [{"role": "assistant", "content": response_text}],
                        config.memory_creation_interval,
                        config.enable_memory_creation,
                    )
                )

            # Format the response for LiteLLM
            completion_id = f"chatcmpl-{uuid.uuid4().hex}"
            model_response.id = completion_id

            # Set choices
            model_response.choices = []
            model_response.choices.append({"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"})

            model_response.created = int(time.time())
            model_response.model = model

            # Calculate token usage
            prompt_tokens = count_tokens(ctx.chat_model.name, augmented_context_messages)
            completion_tokens = count_tokens(
                ctx.chat_model.name,
                ContextMessage(
                    role="assistant",
                    content=response_text,
                    chat_model=ctx.chat_model.name,
                ),
            )

            # Set usage information
            if hasattr(model_response, "usage"):
                model_response.usage = {}
                model_response.usage["prompt_tokens"] = prompt_tokens
                model_response.usage["completion_tokens"] = completion_tokens
                model_response.usage["total_tokens"] = prompt_tokens + completion_tokens

            return model_response

        except Exception as e:
            logger.error(f"Error in ElroyLLM completion: {str(e)}")
            raise ElroyLLMError(status_code=500, message=f"Error in ElroyLLM completion: {str(e)}")

    def streaming(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: Any,
        print_verbose: Callable,
        encoding,
        api_key,
        logging_obj,
        optional_params: dict,
        acompletion=None,
        litellm_params=None,
        logger_fn=None,
        headers={},
        timeout: Optional[Union[float, httpx.Timeout]] = None,
        client: Optional[HTTPHandler] = None,
    ) -> Iterator[Dict]:
        """
        Handle streaming completion requests for Elroy.

        Args:
            model: The model to use for completion
            messages: The messages to process
            api_base: The API base URL
            custom_prompt_dict: Custom prompt dictionary
            model_response: The model response object to populate
            print_verbose: Function for verbose printing
            encoding: The encoding to use
            api_key: The API key
            logging_obj: Logging object
            optional_params: Optional parameters
            acompletion: Async completion function
            litellm_params: LiteLLM parameters
            logger_fn: Logger function
            headers: HTTP headers
            timeout: Request timeout
            client: HTTP client

        Yields:
            Streaming chunks of the response
        """
        try:
            # Create Elroy context
            ctx = ElroyContext(**get_resolved_params(use_background_threads=True))

            # Set up chat model
            chat_model = ChatModel(
                name=model,
                enable_caching=True,
                api_key=api_key,
                provider=Provider.OPENAI,
                inline_tool_calls=False,
                ensure_alternating_roles=True,
            )
            ctx.chat_model = chat_model

            # Get config
            config = get_config()

            # Convert messages to Elroy format
            elroy_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    # Convert dict to proper format expected by convert_openai_message_to_context_message
                    from ..openai_compatible.models import Message, MessageRole

                    role = MessageRole(msg["role"])
                    content = msg.get("content")
                    name = msg.get("name")
                    tool_calls = msg.get("tool_calls")
                    tool_call_id = msg.get("tool_call_id")
                    openai_msg = Message(role=role, content=content, name=name, tool_calls=tool_calls, tool_call_id=tool_call_id)
                    elroy_messages.append(convert_openai_message_to_context_message(openai_msg, chat_model.name))
                else:
                    elroy_messages.append(convert_openai_message_to_context_message(msg, chat_model.name))

            # Get relevant memories
            memories = asyncio.run(
                get_relevant_memories_for_conversation(
                    ctx,
                    messages,
                    config.max_memories_per_request,
                    config.relevance_threshold,
                )
            )

            # Add memories to context
            memory_context_messages = []
            if memories:
                for memory in memories:
                    memory_content = self._get_memory_content(memory)
                    memory_text = f"Memory: {memory.name}\n{memory_content}"
                    memory_context_messages.append(
                        ContextMessage(
                            role="system",
                            content=memory_text,
                            chat_model=chat_model.name,
                        )
                    )

            # Combine system messages, memories, and conversation messages
            system_messages = [msg for msg in elroy_messages if msg.role == "system"]
            non_system_messages = [msg for msg in elroy_messages if msg.role != "system"]

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
            stream_parser = generate_chat_completion_message(
                ctx.chat_model,
                augmented_context_messages,
                [],  # No tools for now
                enable_tools=False,
            )

            # Create a unique ID for this completion
            completion_id = f"chatcmpl-{uuid.uuid4().hex}"
            created_time = int(time.time())

            # First yield the role
            yield {
                "id": completion_id,
                "model": model,
                "created": created_time,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }

            # Stream the response
            response_text = ""

            # Then yield content chunks
            for stream_chunk in stream_parser.process_stream():
                if hasattr(stream_chunk, "content"):
                    response_text += stream_chunk.content

                    yield {
                        "id": completion_id,
                        "model": model,
                        "created": created_time,
                        "choices": [{"index": 0, "delta": {"content": stream_chunk.content}, "finish_reason": None}],
                    }

            # Final chunk with finish reason
            yield {
                "id": completion_id,
                "model": model,
                "created": created_time,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }

            # Process memory creation asynchronously if enabled
            if config.enable_memory_creation:
                asyncio.create_task(
                    process_memory_creation(
                        ctx,
                        messages + [{"role": "assistant", "content": response_text}],
                        config.memory_creation_interval,
                        config.enable_memory_creation,
                    )
                )

        except Exception as e:
            logger.error(f"Error in ElroyLLM streaming: {str(e)}")
            raise ElroyLLMError(status_code=500, message=f"Error in ElroyLLM streaming: {str(e)}")

    async def acompletion(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: Any,
        print_verbose: Callable,
        encoding,
        api_key,
        logging_obj,
        optional_params: dict,
        acompletion=None,
        litellm_params=None,
        logger_fn=None,
        headers={},
        timeout: Optional[Union[float, httpx.Timeout]] = None,
        client: Optional[AsyncHTTPHandler] = None,
    ) -> Any:
        """
        Handle async completion requests for Elroy.

        Args:
            model: The model to use for completion
            messages: The messages to process
            api_base: The API base URL
            custom_prompt_dict: Custom prompt dictionary
            model_response: The model response object to populate
            print_verbose: Function for verbose printing
            encoding: The encoding to use
            api_key: The API key
            logging_obj: Logging object
            optional_params: Optional parameters
            acompletion: Async completion function
            litellm_params: LiteLLM parameters
            logger_fn: Logger function
            headers: HTTP headers
            timeout: Request timeout
            client: HTTP client

        Returns:
            A populated ModelResponse object
        """
        try:
            # Create Elroy context
            ctx = ElroyContext(**get_resolved_params(use_background_threads=True))

            # Set up chat model
            chat_model = ChatModel(
                name=model,
                enable_caching=True,
                api_key=api_key,
                provider=Provider.OPENAI,
                inline_tool_calls=False,
                ensure_alternating_roles=True,
            )
            ctx.chat_model = chat_model

            # Get config
            config = get_config()

            # Convert messages to Elroy format
            elroy_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    # Convert dict to proper format expected by convert_openai_message_to_context_message
                    from ..openai_compatible.models import Message, MessageRole

                    role = MessageRole(msg["role"])
                    content = msg.get("content")
                    name = msg.get("name")
                    tool_calls = msg.get("tool_calls")
                    tool_call_id = msg.get("tool_call_id")
                    openai_msg = Message(role=role, content=content, name=name, tool_calls=tool_calls, tool_call_id=tool_call_id)
                    elroy_messages.append(convert_openai_message_to_context_message(openai_msg, chat_model.name))
                else:
                    elroy_messages.append(convert_openai_message_to_context_message(msg, chat_model.name))

            # Get relevant memories
            memories = await get_relevant_memories_for_conversation(
                ctx,
                messages,
                config.max_memories_per_request,
                config.relevance_threshold,
            )

            # Add memories to context
            memory_context_messages = []
            if memories:
                for memory in memories:
                    memory_content = self._get_memory_content(memory)
                    memory_text = f"Memory: {memory.name}\n{memory_content}"
                    memory_context_messages.append(
                        ContextMessage(
                            role="system",
                            content=memory_text,
                            chat_model=chat_model.name,
                        )
                    )

            # Combine system messages, memories, and conversation messages
            system_messages = [msg for msg in elroy_messages if msg.role == "system"]
            non_system_messages = [msg for msg in elroy_messages if msg.role != "system"]

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
            stream_parser = generate_chat_completion_message(
                ctx.chat_model,
                augmented_context_messages,
                [],  # No tools for now
                enable_tools=False,
            )

            # Collect the response
            response_text = ""
            for chunk in stream_parser.process_stream():
                if hasattr(chunk, "content"):
                    response_text += chunk.content

            # Process memory creation asynchronously if enabled
            if config.enable_memory_creation:
                asyncio.create_task(
                    process_memory_creation(
                        ctx,
                        messages + [{"role": "assistant", "content": response_text}],
                        config.memory_creation_interval,
                        config.enable_memory_creation,
                    )
                )

            # Format the response for LiteLLM
            completion_id = f"chatcmpl-{uuid.uuid4().hex}"
            model_response.id = completion_id

            # Set choices
            model_response.choices = []
            model_response.choices.append({"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"})

            model_response.created = int(time.time())
            model_response.model = model

            # Calculate token usage
            prompt_tokens = count_tokens(ctx.chat_model.name, augmented_context_messages)
            completion_tokens = count_tokens(
                ctx.chat_model.name,
                ContextMessage(
                    role="assistant",
                    content=response_text,
                    chat_model=ctx.chat_model.name,
                ),
            )

            # Set usage information
            if hasattr(model_response, "usage"):
                model_response.usage = {}
                model_response.usage["prompt_tokens"] = prompt_tokens
                model_response.usage["completion_tokens"] = completion_tokens
                model_response.usage["total_tokens"] = prompt_tokens + completion_tokens

            return model_response

        except Exception as e:
            logger.error(f"Error in ElroyLLM acompletion: {str(e)}")
            raise ElroyLLMError(status_code=500, message=f"Error in ElroyLLM acompletion: {str(e)}")

    async def astreaming(
        self,
        model: str,
        messages: list,
        api_base: str,
        custom_prompt_dict: dict,
        model_response: Any,
        print_verbose: Callable,
        encoding,
        api_key,
        logging_obj,
        optional_params: dict,
        acompletion=None,
        litellm_params=None,
        logger_fn=None,
        headers={},
        timeout: Optional[Union[float, httpx.Timeout]] = None,
        client: Optional[AsyncHTTPHandler] = None,
    ) -> AsyncIterator[Dict]:
        """
        Handle async streaming completion requests for Elroy.

        Args:
            model: The model to use for completion
            messages: The messages to process
            api_base: The API base URL
            custom_prompt_dict: Custom prompt dictionary
            model_response: The model response object to populate
            print_verbose: Function for verbose printing
            encoding: The encoding to use
            api_key: The API key
            logging_obj: Logging object
            optional_params: Optional parameters
            acompletion: Async completion function
            litellm_params: LiteLLM parameters
            logger_fn: Logger function
            headers: HTTP headers
            timeout: Request timeout
            client: HTTP client

        Yields:
            Streaming chunks of the response
        """
        try:
            # Create Elroy context
            ctx = ElroyContext(**get_resolved_params(use_background_threads=True))

            # Set up chat model
            chat_model = ChatModel(
                name=model,
                enable_caching=True,
                api_key=api_key,
                provider=Provider.OPENAI,
                inline_tool_calls=False,
                ensure_alternating_roles=True,
            )
            ctx.chat_model = chat_model

            # Get config
            config = get_config()

            # Convert messages to Elroy format
            elroy_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    # Convert dict to proper format expected by convert_openai_message_to_context_message
                    from ..openai_compatible.models import Message, MessageRole

                    role = MessageRole(msg["role"])
                    content = msg.get("content")
                    name = msg.get("name")
                    tool_calls = msg.get("tool_calls")
                    tool_call_id = msg.get("tool_call_id")
                    openai_msg = Message(role=role, content=content, name=name, tool_calls=tool_calls, tool_call_id=tool_call_id)
                    elroy_messages.append(convert_openai_message_to_context_message(openai_msg, chat_model.name))
                else:
                    elroy_messages.append(convert_openai_message_to_context_message(msg, chat_model.name))

            # Get relevant memories
            memories = await get_relevant_memories_for_conversation(
                ctx,
                messages,
                config.max_memories_per_request,
                config.relevance_threshold,
            )

            # Add memories to context
            memory_context_messages = []
            if memories:
                for memory in memories:
                    memory_content = self._get_memory_content(memory)
                    memory_text = f"Memory: {memory.name}\n{memory_content}"
                    memory_context_messages.append(
                        ContextMessage(
                            role="system",
                            content=memory_text,
                            chat_model=chat_model.name,
                        )
                    )

            # Combine system messages, memories, and conversation messages
            system_messages = [msg for msg in elroy_messages if msg.role == "system"]
            non_system_messages = [msg for msg in elroy_messages if msg.role != "system"]

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
            stream_parser = generate_chat_completion_message(
                ctx.chat_model,
                augmented_context_messages,
                [],  # No tools for now
                enable_tools=False,
            )

            # Create a unique ID for this completion
            completion_id = f"chatcmpl-{uuid.uuid4().hex}"
            created_time = int(time.time())

            # First yield the role
            yield {
                "id": completion_id,
                "model": model,
                "created": created_time,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }

            # Stream the response
            response_text = ""

            # Then yield content chunks
            for stream_chunk in stream_parser.process_stream():
                if hasattr(stream_chunk, "content"):
                    response_text += stream_chunk.content

                    yield {
                        "id": completion_id,
                        "model": model,
                        "created": created_time,
                        "choices": [{"index": 0, "delta": {"content": stream_chunk.content}, "finish_reason": None}],
                    }

            # Final chunk with finish reason
            yield {
                "id": completion_id,
                "model": model,
                "created": created_time,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }

            # Process memory creation asynchronously if enabled
            if config.enable_memory_creation:
                asyncio.create_task(
                    process_memory_creation(
                        ctx,
                        messages + [{"role": "assistant", "content": response_text}],
                        config.memory_creation_interval,
                        config.enable_memory_creation,
                    )
                )

        except Exception as e:
            logger.error(f"Error in ElroyLLM astreaming: {str(e)}")
            raise ElroyLLMError(status_code=500, message=f"Error in ElroyLLM astreaming: {str(e)}")
