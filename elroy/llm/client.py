import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel
from toolz import dissoc, pipe
from toolz.curried import keyfilter, map

from ..config.llm import ChatModel, EmbeddingModel
from ..core.constants import (
    ASSISTANT,
    SYSTEM,
    TOOL,
    USER,
    InvalidForceToolError,
    MissingToolCallMessageError,
    Provider,
)
from ..core.logging import get_logger
from ..core.tracing import tracer
from ..repository.context_messages.data_models import ContextMessage
from .stream_parser import StreamParser

logger = get_logger()


@tracer.chain
def generate_chat_completion_message(
    chat_model: ChatModel,
    context_messages: List[ContextMessage],
    tool_schemas: List[Dict[str, Any]],
    enable_tools: bool = True,
    force_tool: Optional[str] = None,
) -> StreamParser:
    """
    Generates a chat completion message.

    tool: Force AI to invoke tool
    """

    if force_tool and not enable_tools:
        logging.error("Force tool requested, but tools are disabled. Ignoring force tool request")
        force_tool = None
    if force_tool and not tool_schemas:
        raise ValueError(f"Requested tool {force_tool}, but no tools available")

    from litellm import completion
    from litellm.exceptions import BadRequestError

    if context_messages[-1].role == ASSISTANT:
        if force_tool:
            context_messages.append(
                ContextMessage(
                    role=USER,
                    content=f"User is requesting tool call: {force_tool}",
                    chat_model=chat_model.name,
                )
            )
        else:
            raise ValueError("Assistant message already the most recent message")

    context_message_dicts = pipe(
        context_messages,
        map(asdict),
        map(keyfilter(lambda k: k not in ("id", "created_at", "memory_metadata", "chat_model"))),
        map(lambda d: dissoc(d, "tool_calls") if not d.get("tool_calls") else d),
        list,
    )

    if chat_model.ensure_alternating_roles:
        USER_HIDDEN_PREFIX = "[This is a system message, representing internal thought process of the assistant]"
        for idx, message in enumerate(context_message_dicts):
            assert isinstance(message, Dict)

            if idx == 0:
                assert message["role"] == SYSTEM, f"First message must be a system message, but found: " + message["role"]

            if idx != 0 and message["role"] == SYSTEM:
                message["role"] = USER
                message["content"] = f"{USER_HIDDEN_PREFIX} {message['content']}"

    if enable_tools and tool_schemas and len(tool_schemas) > 0:
        if force_tool:
            if len(tool_schemas) == 0:
                raise InvalidForceToolError(f"Requested tool {force_tool}, but not tools available")
            elif not any(t["function"]["name"] == force_tool for t in tool_schemas):
                avaliable_tools = ", ".join([t["function"]["name"] for t in tool_schemas])
                raise InvalidForceToolError(f"Requested tool {force_tool} not available. Available tools: {avaliable_tools}")
            else:
                tool_choice = {"type": "function", "function": {"name": force_tool}}
        else:
            tool_choice = "auto"
    else:
        if force_tool:
            raise ValueError(f"Requested tool {force_tool} but model {chat_model.name} does not support tools")
        else:

            if chat_model.provider == Provider.ANTHROPIC and any(m.role == TOOL for m in context_messages):
                # If tool use is in the context window, anthropic requires tools to be enabled and provided
                from ..tools.registry import do_not_use
                from ..tools.schema import get_function_schema

                tool_choice = "auto"
                tool_schemas = [get_function_schema(do_not_use)]  # type: ignore
            else:
                tool_choice = None
                # Models are inconsistent on whether they want None or an empty list when tools are disabled, but most often None seems correct.
                tool_schemas = None  # type: ignore

    try:

        completion_kwargs = _build_completion_kwargs(
            model=chat_model,
            messages=context_message_dicts,  # type: ignore
            stream=True,
            tool_choice=tool_choice,
            tools=tool_schemas,
        )

        return StreamParser(chat_model, completion(**completion_kwargs))  # type: ignore

    except Exception as e:
        if isinstance(e, BadRequestError) and "An assistant message with 'tool_calls' must be followed by tool messages" in str(e):
            raise MissingToolCallMessageError
        else:
            raise e


def query_llm(model: ChatModel, prompt: str, system: str) -> str:
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return _query_llm(model=model, prompt=prompt, system=system, response_format=None)


T = TypeVar("T", bound=BaseModel)


def query_llm_with_response_format(model: ChatModel, prompt: str, system: str, response_format: Type[T]) -> T:
    response = _query_llm(
        model=model,
        prompt=prompt,
        system=system,
        response_format=response_format,
    )

    return response_format.model_validate_json(response)


def query_llm_with_word_limit(model: ChatModel, prompt: str, system: str, word_limit: int) -> str:
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return query_llm(
        prompt="\n".join(
            [
                prompt,
                f"Your word limit is {word_limit}. DO NOT EXCEED IT.",
            ]
        ),
        model=model,
        system=system,
    )


def get_embedding(model: EmbeddingModel, text: str) -> List[float]:
    """
    Generate an embedding for the given text using the specified model.

    Args:
        text (str): The input text to generate an embedding for.
        model (str): The name of the embedding model to use.

    Returns:
        List[float]: The generated embedding as a list of floats.
    """
    from litellm import embedding
    from litellm.exceptions import ContextWindowExceededError

    if not text:
        raise ValueError("Text cannot be empty")
    embedding_kwargs = {
        "model": model.name,
        "input": [text],
        "caching": model.enable_caching,
    }

    if model.api_key:
        embedding_kwargs["api_key"] = model.api_key

    if model.api_base:
        embedding_kwargs["api_base"] = model.api_base

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            response = embedding(**embedding_kwargs)
            return response.data[0]["embedding"]  # type: ignore
        except ContextWindowExceededError:
            new_length = int(len(text) / 2)
            text = text[-new_length:]
            embedding_kwargs["input"] = [text]
            logger.info(f"Context window exceeded, retrying with shorter message of length {new_length}")
    raise RuntimeError(f"Context window exceeded despite {max_attempts} attempt to shorten input")


def _build_completion_kwargs(
    model: ChatModel,
    messages: List[Dict[str, str]],
    stream: bool,
    tool_choice: Union[str, Dict, None],
    tools: Optional[List[Dict[str, Any]]],
    response_format: Optional[Type[BaseModel]] = None,
) -> Dict[str, Any]:
    """Centralized configuration for LLM requests"""
    kwargs = {
        "messages": messages,
        "model": model.name,
        "caching": model.enable_caching,
        "tool_choice": tool_choice,
        "tools": tools,
        "response_format": response_format,
    }
    if model.api_key:
        kwargs["api_key"] = model.api_key

    if model.api_base:
        kwargs["api_base"] = model.api_base
    if stream:
        kwargs["stream"] = True

    return kwargs


def _query_llm(model: ChatModel, prompt: str, system: str, response_format: Optional[Type[BaseModel]]) -> str:
    from litellm import completion

    messages = [{"role": SYSTEM, "content": system}, {"role": USER, "content": prompt}]
    completion_kwargs = _build_completion_kwargs(
        model=model,
        messages=messages,
        stream=False,
        tool_choice=None,
        tools=None,
        response_format=response_format,
    )
    return completion(**completion_kwargs).choices[0].message.content.strip()  # type: ignore
