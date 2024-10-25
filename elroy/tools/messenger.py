import logging
from dataclasses import asdict
from functools import partial
from typing import Dict, Iterator, List, NamedTuple, Optional, Union

from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall
from toolz import concat, juxt, pipe
from toolz.curried import do, filter, map, remove, tail

from elroy.config import ElroyContext
from elroy.llm.client import generate_chat_completion_message, get_embedding
from elroy.store.data_models import ASSISTANT, TOOL, USER, EmbeddableSqlModel, Goal, Memory
from elroy.store.embeddings import (get_most_relevant_goal,
                                    get_most_relevant_memory)
from elroy.store.message import (ContextMessage, MemoryMetadata,
                                 add_context_messages, get_context_messages,
                                 remove_context_messages)
from elroy.system.utils import logged_exec_time
from elroy.tools.function_caller import (FunctionCall, PartialToolCall,
                                         exec_function_call)
from elroy.tools.functions.user_preferences import get_user_preferred_name


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
    from elroy.system_context import get_refreshed_system_message
    
    assert role in [USER, ASSISTANT]

    context_messages = get_context_messages(context)

    # if context messages is empty, add system message to init. else add new message and any relevant memories
    new_messages = (
        [get_refreshed_system_message(get_user_preferred_name(context), [])]
        if not context_messages
        else [] + [ContextMessage(role=USER, content=msg)] + get_relevant_memories(context, context_messages)
    )

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


def is_memory_in_context(context_messages: List[ContextMessage], memory: EmbeddableSqlModel) -> bool:
    return pipe(
        context_messages,
        map(lambda x: x.memory_metadata),
        filter(lambda x: x is not None),
        concat,
        filter(lambda x: x.memory_type == memory.__class__.__name__ and x.id == memory.id),
        list,
        lambda x: len(x) > 0,
    )


def remove_from_context(context: ElroyContext, memory: EmbeddableSqlModel):
    id = memory.id
    assert id
    remove_memory_from_context(memory.__class__.__name__, context, id)


def remove_memory_from_context(memory_type: str, context: ElroyContext, memory_id: int) -> None:
    def is_memory_in_context_message(msg: ContextMessage) -> bool:
        if not msg.memory_metadata:
            return False

        return any(x.memory_type == memory_type and x.id == memory_id for x in msg.memory_metadata)

    pipe(
        get_context_messages(context),
        filter(is_memory_in_context_message),
        list,
        partial(remove_context_messages, context),
    )




@logged_exec_time
def get_relevant_memories(context: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:

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
                content=str(x.to_fact()),
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
    for chunk in generate_chat_completion_message([asdict(x) for x in context_messages]):
        if chunk.choices[0].delta.content:  # type: ignore
            yield ContentItem(content=chunk.choices[0].delta.content)  # type: ignore
        if chunk.choices[0].delta.tool_calls:  # type: ignore
            yield from tool_call_accumulator.update(chunk.choices[0].delta.tool_calls)  # type: ignore
