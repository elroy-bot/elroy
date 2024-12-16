import logging
from dataclasses import asdict
from typing import Any, Dict, Iterator, List

from toolz import pipe
from toolz.curried import keyfilter, map

from ..config.config import ChatModel, EmbeddingModel
from ..config.constants import (
    MAX_CHAT_COMPLETION_RETRY_COUNT,
    MaxRetriesExceededError,
    MissingToolCallMessageError,
)
from ..config.models import get_fallback_model
from ..repository.data_models import SYSTEM, USER, ContextMessage
from ..utils.utils import logged_exec_time


@logged_exec_time
def generate_chat_completion_message(
    chat_model: ChatModel, context_messages: List[ContextMessage], retry_number: int = 0
) -> Iterator[Dict]:
    from litellm import completion
    from litellm.exceptions import BadRequestError, InternalServerError, RateLimitError

    context_message_dicts = pipe(
        context_messages,
        map(asdict),
        map(keyfilter(lambda k: k not in ("id", "created_at", "memory_metadata", "chat_model"))),
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

    try:
        completion_kwargs = _build_completion_kwargs(
            model=chat_model,
            messages=context_message_dicts,  # type: ignore
            stream=True,
            use_tools=chat_model.supports_tools,
        )
        return completion(**completion_kwargs)  # type: ignore
    except Exception as e:
        if isinstance(e, BadRequestError):
            if "An assistant message with 'tool_calls' must be followed by tool messages" in str(e):
                raise MissingToolCallMessageError
        elif isinstance(e, InternalServerError) or isinstance(e, RateLimitError):
            if retry_number >= MAX_CHAT_COMPLETION_RETRY_COUNT:
                raise MaxRetriesExceededError()
            else:
                fallback_model = get_fallback_model(chat_model)
                if fallback_model:
                    logging.info(
                        f"Rate limit or internal server error for model {chat_model.name}, falling back to model {fallback_model.name}"
                    )
                    return generate_chat_completion_message(fallback_model, context_messages, retry_number + 1)
                else:
                    logging.error(f"No fallback model available for {chat_model.name}, aborting")
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
        "model": model.model,
        "input": [text],
        "caching": model.enable_caching,
        "api_key": model.api_key,
    }

    if model.api_base:
        embedding_kwargs["api_base"] = model.api_base
    if model.organization:
        embedding_kwargs["organization"] = model.organization

    response = embedding(**embedding_kwargs)
    return response.data[0]["embedding"]


def _build_completion_kwargs(
    model: ChatModel,
    messages: List[Dict[str, str]],
    stream: bool,
    use_tools: bool,
) -> Dict[str, Any]:
    """Centralized configuration for LLM requests"""
    kwargs = {
        "messages": messages,
        "model": model.name,
        "api_key": model.api_key,
        "caching": model.enable_caching,
    }

    if model.api_base:
        kwargs["api_base"] = model.api_base
    if model.organization:
        kwargs["organization"] = model.organization

    if use_tools:
        from ..tools.function_caller import get_function_schemas

        kwargs.update(
            {
                "tool_choice": "auto",
                "tools": get_function_schemas(),
            }
        )

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
        use_tools=False,
    )
    return completion(**completion_kwargs).choices[0].message.content  # type: ignore
