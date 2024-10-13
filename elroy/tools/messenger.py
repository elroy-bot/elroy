import logging
from dataclasses import asdict
from functools import partial
from typing import Dict, Iterator, List, NamedTuple, Optional, Union

from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall
from sqlmodel import Session
from toolz import concat, juxt, pipe
from toolz.curried import do, filter, map, remove, tail

from elroy.llm.client import generate_chat_completion_message, get_embedding
from elroy.store.data_models import EmbeddableSqlModel
from elroy.store.embeddings import (get_most_relevant_archival_memory,
                                    get_most_relevant_goal)
from elroy.store.message import (ContextMessage, MemoryMetadata,
                                 get_context_messages,
                                 replace_context_messages)
from elroy.system.utils import logged_exec_time
from elroy.tools.function_caller import (FunctionCall, PartialToolCall,
                                         exec_function_call)
from elroy.tools.functions.user_preferences import get_user_preferred_name
from elroy.tools.system_commands import (invoke_system_command,
                                         is_system_command)
from elroy.ui.loading_message import cli_loading


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


def process_message(session: Session, user_id: int, msg: str) -> Iterator[str]:
    if is_system_command(msg):
        yield invoke_system_command(session, user_id, msg)
    else:
        from elroy.memory.system_context import get_refreshed_system_message

        context_messages = pipe(
            get_context_messages(session, user_id),
            lambda x: (
                [get_refreshed_system_message(get_user_preferred_name(session, user_id), [])] + x if not x else x
            ),  # append new system message if it is missing
            lambda x: x + [ContextMessage(role="user", content=msg)],
            lambda x: x + get_relevant_memories(session, user_id, x),
        )

        full_content = ""

        while True:
            function_calls: List[FunctionCall] = []
            tool_context_messages: List[ContextMessage] = []

            for stream_chunk in _generate_assistant_reply(context_messages):
                if isinstance(stream_chunk, ContentItem):
                    full_content += stream_chunk.content
                    yield stream_chunk.content
                elif isinstance(stream_chunk, FunctionCall):
                    pipe(
                        stream_chunk,
                        do(function_calls.append),
                        lambda x: ContextMessage(
                            role="tool",
                            tool_call_id=x.id,
                            content=exec_function_call(session, user_id, x),
                        ),
                        tool_context_messages.append,
                    )
            context_messages.append(
                ContextMessage(
                    role="assistant",
                    content=full_content,
                    tool_calls=(None if not function_calls else [f.to_tool_call() for f in function_calls]),
                )
            )

            if not tool_context_messages:
                replace_context_messages(session, user_id, context_messages)
                break
            else:
                context_messages += tool_context_messages


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


def remove_memory_from_context(context_messages: List[ContextMessage], memory_type: str, memory_id: int) -> List[ContextMessage]:
    return pipe(
        context_messages,
        filter(
            lambda x: not (x.memory_metadata and x.memory_metadata[0].memory_type == memory_type and x.memory_metadata[0].id == memory_id)
        ),
        list,
    )


@cli_loading("Searching for relevant memories...")
@logged_exec_time
def get_relevant_memories(session: Session, user_id: int, context_messages: List[ContextMessage]) -> List[ContextMessage]:

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
        lambda x: juxt(get_most_relevant_goal, get_most_relevant_archival_memory)(session, user_id, x),
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

    if context_messages[-1].role == "assistant":
        raise ValueError("Assistant message already the most recent message")

    tool_call_accumulator = ToolCallAccumulator()
    for chunk in generate_chat_completion_message([asdict(x) for x in context_messages]):
        if chunk.choices[0].delta.content:
            yield ContentItem(content=chunk.choices[0].delta.content)
        if chunk.choices[0].delta.tool_calls:
            yield from tool_call_accumulator.update(chunk.choices[0].delta.tool_calls)

    # except MissingToolCallIdError:
    #     logging.error("Attempting to repair missing tool call ID")
    #     new_context_messages = []
    #     for msg in reversed(context_messages):
    #         if msg.role != "assistant" or not msg.tool_calls:
    #             new_context_messages = [msg] + new_context_messages
    #         else:
    #             for tool_call in msg.tool_calls:
    #                 if any(m.tool_call_id == tool_call.id for m in new_context_messages):
    #                     new_context_messages = [msg] + new_context_messages
    #                 else:
    #                     logging.error(f"Dropping assistant message without corresponding tool call message. ID: {msg.id}")
    #                     continue
    #     if len(context_messages) == len(new_context_messages):
    #         raise ValueError("Could not repair missing tool call ID")
    #     logging.error(f"Dropping {len(context_messages) - len(new_context_messages)} context messages for user {user_id}")
    #     context_messages = new_context_messages

    # if context_messages[-1].role == "assistant":
    #     return iter([]), context_messages[-1]
    # else:
    #     return _generate_assistant_reply(
    #         session,
    #         user_id,
    #         context_messages,
    #         recursion_count + 1,
    #     )
