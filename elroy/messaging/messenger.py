import logging
from functools import partial
from typing import Dict, Iterator, List, NamedTuple, Optional, Union

from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall
from toolz import juxt, pipe
from toolz.curried import do, filter, map, remove, tail

from ..config.config import ElroyContext
from ..llm.client import generate_chat_completion_message, get_embedding
from ..repository.data_models import ASSISTANT, SYSTEM, TOOL, USER
from ..repository.embeddings import get_most_relevant_goal, get_most_relevant_memory
from ..repository.facts import to_fact
from ..repository.message import (
    ContextMessage,
    MemoryMetadata,
    add_context_messages,
    get_context_messages,
)
from ..tools.function_caller import FunctionCall, PartialToolCall, exec_function_call
from ..utils.utils import logged_exec_time


class ToolCallAccumulator:
    def __init__(self):
        self.tool_calls: Dict[int, PartialToolCall] = {}
        self.last_updated_index: Optional[int] = None

    def update(self, delta_tool_calls: Optional[List[ChoiceDeltaToolCall]]) -> Iterator[FunctionCall]:
        for delta in delta_tool_calls or []:
            if delta.index not in self.tool_calls:
                if (
                    self.last_updated_index is not None
                    and self.last_updated_index in self.tool_calls
                    and self.last_updated_index != delta.index
                ):
                    raise ValueError("New tool call started, but old one is not yet complete")
                assert delta.id
                self.tool_calls[delta.index] = PartialToolCall(id=delta.id)

            completed_tool_call = self.tool_calls[delta.index].update(delta)
            if completed_tool_call:
                self.tool_calls.pop(delta.index)
                yield completed_tool_call
            else:
                self.last_updated_index = delta.index


def process_message(context: ElroyContext, msg: str, role: str = USER) -> Iterator[str]:
    assert role in [USER, ASSISTANT, SYSTEM]

    context_messages = get_context_messages(context)

    new_messages = [ContextMessage(role=role, content=msg)] + get_relevant_memories(context, context_messages)

    full_content = ""

    while True:
        function_calls: List[FunctionCall] = []
        tool_context_messages: List[ContextMessage] = []

        for stream_chunk in _generate_assistant_reply(context_messages + new_messages):
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
                    ),
                    tool_context_messages.append,
                )
        new_messages.append(
            ContextMessage(
                role=ASSISTANT,
                content=full_content,
                tool_calls=(None if not function_calls else [f.to_tool_call() for f in function_calls]),
            )
        )

        if not tool_context_messages:
            add_context_messages(context, new_messages)
            break
        else:
            new_messages += tool_context_messages


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
        get_embedding,
        lambda x: juxt(get_most_relevant_goal, get_most_relevant_memory)(context, x),
        filter(lambda x: x is not None),
        remove(partial(is_memory_in_context, context_messages)),
        map(
            lambda x: ContextMessage(
                role="system",
                memory_metadata=[MemoryMetadata(memory_type=x.__class__.__name__, id=x.id, name=x.get_name())],
                content=to_fact(x),
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
    context_messages: List[ContextMessage],
    recursion_count: int = 0,
) -> Iterator[StreamItem]:
    if recursion_count >= 10:
        raise ValueError("Exceeded maximum number of chat completion attempts")
    elif recursion_count > 0:
        logging.info(f"Recursion count: {recursion_count}")

    if context_messages[-1].role == ASSISTANT:
        raise ValueError("Assistant message already the most recent message")

    tool_call_accumulator = ToolCallAccumulator()
    for chunk in generate_chat_completion_message(context_messages):
        if chunk.choices[0].delta.content:  # type: ignore
            yield ContentItem(content=chunk.choices[0].delta.content)  # type: ignore
        if chunk.choices[0].delta.tool_calls:  # type: ignore
            yield from tool_call_accumulator.update(chunk.choices[0].delta.tool_calls)  # type: ignore
