import logging
from functools import partial
from typing import Dict, Iterator, List, NamedTuple, Optional, Union

from litellm.types.utils import ChatCompletionDeltaToolCall
from toolz import juxt, pipe
from toolz.curried import do, filter, map, remove, tail

from ..config.config import ChatModel, ElroyContext
from ..llm.client import (
    MissingAssistantToolCallError,
    MissingToolCallMessageError,
    generate_chat_completion_message,
    get_embedding,
)
from ..repository.data_models import ASSISTANT, SYSTEM, TOOL, USER
from ..repository.embeddings import get_most_relevant_goal, get_most_relevant_memory
from ..repository.facts import to_fact
from ..repository.message import (
    ContextMessage,
    MemoryMetadata,
    get_context_messages,
    replace_context_messages,
)
from ..tools.function_caller import FunctionCall, PartialToolCall, exec_function_call
from ..utils.utils import last_or_none, logged_exec_time


class ToolCallAccumulator:
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
                self.tool_calls[delta.index] = PartialToolCall(id=delta.id, model=self.chat_model.model)

            completed_tool_call = self.tool_calls[delta.index].update(delta)
            if completed_tool_call:
                self.tool_calls.pop(delta.index)
                yield completed_tool_call
            else:
                self.last_updated_index = delta.index


def process_message(context: ElroyContext, msg: str, role: str = USER) -> Iterator[str]:
    assert role in [USER, ASSISTANT, SYSTEM]

    context_messages = pipe(
        get_context_messages(context),
        partial(validate_context_messages, context.config.debugging_mode),
        list,
        lambda x: x + [ContextMessage(role=role, content=msg, chat_model=None)],
        lambda x: x + get_relevant_memories(context, x),
        list,
    )

    full_content = ""

    while True:
        function_calls: List[FunctionCall] = []
        tool_context_messages: List[ContextMessage] = []

        for stream_chunk in _generate_assistant_reply(context.config.chat_model, context_messages):
            if isinstance(stream_chunk, ContentItem):
                full_content += stream_chunk.content
                yield stream_chunk.content
            elif isinstance(stream_chunk, FunctionCall):
                pipe(
                    stream_chunk,
                    do(function_calls.append),
                    lambda x: ContextMessage(
                        role=TOOL,
                        tool_call_id=x.id,
                        content=exec_function_call(context, x),
                        chat_model=context.config.chat_model.model,
                    ),
                    tool_context_messages.append,
                )
        context_messages.append(
            ContextMessage(
                role=ASSISTANT,
                content=full_content,
                tool_calls=(None if not function_calls else [f.to_tool_call() for f in function_calls]),
                chat_model=context.config.chat_model.model,
            )
        )

        if not tool_context_messages:
            replace_context_messages(context, context_messages)
            break
        else:
            context_messages += tool_context_messages


def validate_context_messages(debugging_mode: bool, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    if not context_messages or context_messages[0].role != SYSTEM:
        error_msg = (
            f"First message must be a system message, but found: " + context_messages[0].role if context_messages else "No messages found"
        )
        if debugging_mode:
            raise ValueError(error_msg)
        else:
            logging.error(error_msg)
            logging.warning("Attempting to repair by adding a system message to the beginning of the context messages")
            context_messages.insert(0, ContextMessage(role=SYSTEM, content="You are Elroy, a helpful assistant.", chat_model=None))

    for idx, message in enumerate(context_messages):
        if message.role == ASSISTANT and message.tool_calls is not None:
            if idx == len(context_messages) - 1 or context_messages[idx + 1].role != TOOL:
                error_msg = f"Assistant message with tool_calls not followed by tool message: ID = {message.id}"
                if debugging_mode:
                    raise MissingToolCallMessageError(error_msg)
                else:
                    logging.error(error_msg)
                    logging.warning(f"Attempting to repair by removing tool_calls from message {message.id}")
                    message.tool_calls = None

    validated_context_messages = []
    for idx, message in enumerate(context_messages):
        if message.role == TOOL and not _has_assistant_tool_call(message.tool_call_id, context_messages[:idx]):
            error_msg = f"Tool message without preceding assistant message with tool_calls: ID = {message.id}"
            if debugging_mode:
                raise MissingAssistantToolCallError(error_msg)
            else:
                logging.error(error_msg)
                logging.warning(f"Attempting to repair by removing tool message {message.id}")
                continue
        else:
            validated_context_messages.append(message)

    return validated_context_messages


def _has_assistant_tool_call(tool_call_id: Optional[str], context_messages: List[ContextMessage]) -> bool:
    if not tool_call_id:
        logging.warning("Tool call ID is None")
        return False

    return pipe(
        context_messages,
        filter(lambda x: x.role == ASSISTANT),
        last_or_none,
        lambda msg: msg.tool_calls or [] if msg else [],
        map(lambda x: x.id),
        filter(lambda x: x == tool_call_id),
        list,
        lambda x: len(x) > 0,
    )


@logged_exec_time
def get_relevant_memories(context: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    from .context import is_memory_in_context

    message_content = pipe(
        context_messages,
        remove(lambda x: x.role == "system"),
        tail(4),
        map(lambda x: f"{x.role}: {x.content}" if x.content else None),
        remove(lambda x: x is None),
        list,
        "\n".join,
    )

    if not message_content:
        return []

    assert isinstance(message_content, str)

    new_memory_messages = pipe(
        message_content,
        partial(get_embedding, context.config.embedding_model),
        lambda x: juxt(get_most_relevant_goal, get_most_relevant_memory)(context, x),
        filter(lambda x: x is not None),
        remove(partial(is_memory_in_context, context_messages)),
        map(
            lambda x: ContextMessage(
                role="system",
                memory_metadata=[MemoryMetadata(memory_type=x.__class__.__name__, id=x.id, name=x.get_name())],
                content="Information recalled from assistant memory: " + to_fact(x),
                chat_model=None,
            )
        ),
        list,
    )

    return new_memory_messages


from typing import Iterator


class ContentItem(NamedTuple):
    content: str


StreamItem = Union[ContentItem, FunctionCall]


def _generate_assistant_reply(
    chat_model: ChatModel,
    context_messages: List[ContextMessage],
) -> Iterator[StreamItem]:

    if context_messages[-1].role == ASSISTANT:
        raise ValueError("Assistant message already the most recent message")

    tool_call_accumulator = ToolCallAccumulator(chat_model)
    for chunk in generate_chat_completion_message(chat_model, context_messages):
        if chunk.choices[0].delta.content:  # type: ignore
            yield ContentItem(content=chunk.choices[0].delta.content)  # type: ignore
        if chunk.choices[0].delta.tool_calls:  # type: ignore
            yield from tool_call_accumulator.update(chunk.choices[0].delta.tool_calls)  # type: ignore
