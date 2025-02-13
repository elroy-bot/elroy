import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Union

from toolz import dissoc, pipe
from toolz.curried import keyfilter, map

from ..config.constants import (
    ASSISTANT,
    MAX_CHAT_COMPLETION_RETRY_COUNT,
    SYSTEM,
    TOOL,
    USER,
    InvalidForceToolError,
    MaxRetriesExceededError,
    MissingToolCallMessageError,
    Provider,
)
from ..config.llm import ChatModel, EmbeddingModel
from ..config.models_aliases import get_fallback_model
from ..repository.context_messages.data_models import ContextMessage
from .stream_parser import StreamParser


def generate_chat_completion_message(
    chat_model: ChatModel,
    context_messages: List[ContextMessage],
    tool_schemas: List[Dict[str, Any]],
    enable_tools: bool = True,
    force_tool: Optional[str] = None,
    retry_number: int = 0,
) -> StreamParser:
    """
    Generates a chat completion message.

    tool: Force AI to invoke tool
    """

    if force_tool and not enable_tools:
        logging.error("Force tool requested, but tools are disabled. Ignoring force tool request")
        force_tool = None

    from litellm import completion
    from litellm.exceptions import BadRequestError, InternalServerError, RateLimitError

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

    if enable_tools:

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
        if isinstance(e, BadRequestError):
            if "An assistant message with 'tool_calls' must be followed by tool messages" in str(e):
                raise MissingToolCallMessageError
            else:
                raise e
        elif isinstance(e, InternalServerError) or isinstance(e, RateLimitError):
            if retry_number >= MAX_CHAT_COMPLETION_RETRY_COUNT:
                raise MaxRetriesExceededError()
            else:
                fallback_model = get_fallback_model(chat_model)
                if fallback_model:
                    logging.info(
                        f"Rate limit or internal server error for model {chat_model.name}, falling back to model {fallback_model.name}"
                    )
                    return generate_chat_completion_message(
                        fallback_model,
                        context_messages,
                        tool_schemas,
                        enable_tools,
                        force_tool,
                        retry_number + 1,
                    )
                else:
                    logging.error(f"No fallback model available for {chat_model.name}, aborting")
                    raise e
        else:
            raise e


def query_llm(model: ChatModel, prompt: str, system: str) -> str:
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return _query_llm(model=model, prompt=prompt, system=system)


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

    if not text:
        raise ValueError("Text cannot be empty")
    embedding_kwargs = {
        "model": model.name,
        "input": [text],
        "caching": model.enable_caching,
        "api_key": model.api_key,
    }

    if model.api_base:
        embedding_kwargs["api_base"] = model.api_base

    response = embedding(**embedding_kwargs)
    return response.data[0]["embedding"]


def _build_completion_kwargs(
    model: ChatModel,
    messages: List[Dict[str, str]],
    stream: bool,
    tool_choice: Union[str, Dict, None],
    tools: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Centralized configuration for LLM requests"""
    kwargs = {
        "messages": messages,
        "model": model.name,
        "caching": model.enable_caching,
        "tool_choice": tool_choice,
        "tools": tools,
    }
    if model.api_key:
        kwargs["api_key"] = model.api_key

    if model.api_base:
        kwargs["api_base"] = model.api_base
    if stream:
        kwargs["stream"] = True

    return kwargs


def _query_llm(model: ChatModel, prompt: str, system: str) -> str:
    from litellm import completion

    messages = [{"role": SYSTEM, "content": system}, {"role": USER, "content": prompt}]
    completion_kwargs = _build_completion_kwargs(
        model=model,
        messages=messages,
        stream=False,
        tool_choice=None,
        tools=None,
    )
    return completion(**completion_kwargs).choices[0].message.content  # type: ignore
