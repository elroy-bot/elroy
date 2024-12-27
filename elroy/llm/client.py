import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterator, List, Optional, Union

from toolz import dissoc, pipe
from toolz.curried import keyfilter, map

from ..config.config import ChatModel, EmbeddingModel
from ..config.constants import (
    MAX_CHAT_COMPLETION_RETRY_COUNT,
    SYSTEM,
    USER,
    InvalidForceToolError,
    MaxRetriesExceededError,
    MissingToolCallMessageError,
)
from ..config.models import get_fallback_model
from ..db.db_models import ASSISTANT, FunctionCall
from ..repository.data_models import ContentItem, ContextMessage
from ..utils.utils import logged_exec_time


@logged_exec_time
def generate_chat_completion_message(
    chat_model: ChatModel,
    context_messages: List[ContextMessage],
    enable_tools: bool = True,
    force_tool: Optional[str] = None,
    retry_number: int = 0,
) -> Iterator[Dict]:
    """
    Generates a chat completion message.

    tool: Force AI to invoke tool
    """

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
        from ..tools.function_caller import get_function_schemas

        if force_tool:
            tools = get_function_schemas()
            if len(tools) == 0:
                raise InvalidForceToolError(f"Requested tool {force_tool}, but not tools available")
            elif not any(t["function"]["name"] == force_tool for t in tools):
                avaliable_tools = ", ".join([t["function"]["name"] for t in tools])
                raise InvalidForceToolError(f"Requested tool {force_tool} not available. Available tools: {avaliable_tools}")
            else:
                tool_choice = {"type": "function", "function": {"name": force_tool}}
        else:
            tools = get_function_schemas()
            tool_choice = "auto"
    else:
        if force_tool:
            raise ValueError(f"Requested tool {force_tool} but model {chat_model.name} does not support tools")
        else:
            tool_choice = None
            tools = None

    try:
        completion_kwargs = _build_completion_kwargs(
            model=chat_model,
            messages=context_message_dicts,  # type: ignore
            stream=True,
            tool_choice=tool_choice,
            tools=tools,
        )

        tool_call_accumulator = ToolCallAccumulator(chat_model)
        for chunk in completion(**completion_kwargs):
            if chunk.choices[0].delta.content:  # type: ignore
                yield ContentItem(content=chunk.choices[0].delta.content)  # type: ignore
            if chunk.choices[0].delta.tool_calls:  # type: ignore
                yield from tool_call_accumulator.update(chunk.choices[0].delta.tool_calls)  # type: ignore

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
                    yield from generate_chat_completion_message(
                        fallback_model, context_messages, enable_tools, force_tool, retry_number + 1
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
    tool_choice: Union[str, Dict, None],
    tools: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Centralized configuration for LLM requests"""
    kwargs = {
        "messages": messages,
        "model": model.name,
        "api_key": model.api_key,
        "caching": model.enable_caching,
        "tool_choice": tool_choice,
        "tools": tools,
    }

    if model.api_base:
        kwargs["api_base"] = model.api_base
    if model.organization:
        kwargs["organization"] = model.organization
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


class ToolCallAccumulator:
    from litellm.types.utils import ChatCompletionDeltaToolCall

    def __init__(self, chat_model: ChatModel):
        self.chat_model = chat_model
        self.tool_calls: Dict[int, PartialToolCall] = {}
        self.last_updated_index: Optional[int] = None

    def update(self, delta_tool_calls: Optional[List[ChatCompletionDeltaToolCall]]) -> Iterator[FunctionCall]:
        for delta in delta_tool_calls or []:
            if delta.index not in self.tool_calls:
                if (
                    self.last_updated_index is not None
                    and self.last_updated_index in self.tool_calls
                    and self.last_updated_index != delta.index
                ):
                    raise ValueError("New tool call started, but old one is not yet complete")
                assert delta.id
                self.tool_calls[delta.index] = PartialToolCall(id=delta.id, model=self.chat_model.name)

            completed_tool_call = self.tool_calls[delta.index].update(delta)
            if completed_tool_call:
                self.tool_calls.pop(delta.index)
                yield completed_tool_call
            else:
                self.last_updated_index = delta.index


@dataclass
class PartialToolCall:
    id: str
    model: str  # Add model parameter to determine format
    function_name: str = ""
    arguments: str = ""
    type: str = "function"
    is_complete: bool = False

    from litellm.types.utils import ChatCompletionDeltaToolCall

    def update(self, delta: ChatCompletionDeltaToolCall) -> Optional[FunctionCall]:
        from litellm.types.utils import ChatCompletionDeltaToolCall

        if self.is_complete:
            raise ValueError("PartialToolCall is already complete")

        assert isinstance(delta, ChatCompletionDeltaToolCall), f"Expected ChoiceDeltaToolCall, got {type(delta)}"
        assert delta.function
        if delta.function.name:
            self.function_name += delta.function.name
        if delta.function.arguments:
            self.arguments += delta.function.arguments

        # Check if we have a complete JSON object for arguments
        try:
            function_call = FunctionCall(
                id=self.id,
                function_name=self.function_name,
                arguments=json.loads(self.arguments),
            )
            self.is_complete = True
            return function_call
        except json.JSONDecodeError:
            return None
