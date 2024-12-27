import logging
from functools import partial
from typing import Iterator, List, Optional

from toolz import juxt, pipe
from toolz.curried import do, filter, map, remove, tail

from ..config.constants import (
    SYSTEM,
    SYSTEM_INSTRUCTION_LABEL,
    TOOL,
    USER,
    MisplacedSystemInstructError,
    MissingAssistantToolCallError,
    MissingSystemInstructError,
    MissingToolCallMessageError,
)
from ..config.ctx import ElroyContext
from ..db.db_models import ASSISTANT
from ..llm.client import generate_chat_completion_message, get_embedding
from ..repository.data_models import ContentItem, ContextMessage
from ..repository.embeddings import get_most_relevant_goal, get_most_relevant_memory
from ..repository.message import (
    MemoryMetadata,
    get_context_messages,
    is_system_instruction,
    replace_context_messages,
)
from ..tools.function_caller import FunctionCall, exec_function_call
from ..utils.utils import last_or_none, logged_exec_time


def process_message(role: str, ctx: ElroyContext, msg: str, force_tool: Optional[str] = None) -> Iterator[str]:
    assert role in [USER, ASSISTANT, SYSTEM]

    context_messages = pipe(
        get_context_messages(ctx),
        partial(validate, ctx),
        list,
        lambda x: x + [ContextMessage(role=role, content=msg, chat_model=None)],
        lambda x: x + get_relevant_memories(ctx, x),
        list,
    )

    full_content = ""

    while True:
        function_calls: List[FunctionCall] = []
        tool_context_messages: List[ContextMessage] = []

        for stream_chunk in generate_chat_completion_message(ctx.chat_model, context_messages, ctx.enable_tools, force_tool):
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
                        content=exec_function_call(ctx, x),
                        chat_model=ctx.chat_model.name,
                    ),
                    tool_context_messages.append,
                )
        context_messages.append(
            ContextMessage(
                role=ASSISTANT,
                content=full_content,
                tool_calls=(None if not function_calls else [f.to_tool_call() for f in function_calls]),
                chat_model=ctx.chat_model.name,
            )
        )

        if force_tool:
            assert len(tool_context_messages) >= 1
            if len(tool_context_messages) > 1:
                logging.warning(f"With force tool {force_tool}, expected one tool message, but found {len(tool_context_messages)}")

            context_messages += tool_context_messages
            replace_context_messages(ctx, context_messages)

            content = tool_context_messages[-1].content
            assert isinstance(content, str)
            yield content
            break

        elif tool_context_messages:
            context_messages += tool_context_messages
        else:
            replace_context_messages(ctx, context_messages)
            break


def validate(ctx: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    return pipe(
        context_messages,
        partial(_validate_system_instruction_correctly_placed, ctx.debug),
        partial(_validate_assistant_tool_calls_followed_by_tool, ctx.debug),
        partial(_validate_tool_messages_have_assistant_tool_call, ctx.debug),
        lambda msgs: (
            msgs if not ctx.chat_model.ensure_alternating_roles else validate_first_user_precedes_first_assistant(ctx.debug, msgs)
        ),
        list,
    )


def validate_first_user_precedes_first_assistant(debug_mode: bool, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    user_and_assistant_messages = [m for m in context_messages if m.role in [USER, ASSISTANT]]

    if user_and_assistant_messages and user_and_assistant_messages[0].role != USER:
        if debug_mode:
            raise ValueError("First non-system message must be USER role for this model")
        else:
            context_messages = [
                context_messages[0],
                ContextMessage(role=USER, content="The user has begun the converstaion", chat_model=None),
            ] + context_messages[1:]
    return context_messages


def _validate_system_instruction_correctly_placed(debug_mode: bool, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    validated_messages = []
    for idx, message in enumerate(context_messages):
        if idx == 0 and not is_system_instruction(message):
            if debug_mode:
                raise MissingSystemInstructError()
            else:
                logging.error(f"First message is not system instruction, repairing by inserting system instruction")
                validated_messages += [
                    ContextMessage(role=SYSTEM, content=f"{SYSTEM_INSTRUCTION_LABEL}\nYou are a helpful assistant.", chat_model=None),
                    message,
                ]
        elif idx != 0 and is_system_instruction(message):
            if debug_mode:
                raise MisplacedSystemInstructError()
            else:
                logging.error("Found system message in non-first position, repairing by dropping message")
                continue
        else:
            validated_messages.append(message)
    return validated_messages


def _validate_assistant_tool_calls_followed_by_tool(debug_mode: bool, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    """
    Validates that any assistant message with non-empty tool_calls is followed by corresponding tool messages.
    """

    for idx, message in enumerate(context_messages):
        if (message.role == ASSISTANT and message.tool_calls is not None) and (
            idx == len(context_messages) - 1 or context_messages[idx + 1].role != TOOL
        ):
            if debug_mode:
                raise MissingToolCallMessageError()
            else:
                logging.error(
                    f"Assistant message with tool_calls not followed by tool message: ID = {message.id}, repairing by removing tool_calls"
                )
                message.tool_calls = None
    return context_messages


def _validate_tool_messages_have_assistant_tool_call(debug_mode: bool, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    """
    Validates that all tool messages have a preceding assistant message with the corresponding tool_calls.
    """

    validated_context_messages = []
    for idx, message in enumerate(context_messages):
        if message.role == TOOL and not _has_assistant_tool_call(message.tool_call_id, context_messages[:idx]):
            if debug_mode:
                raise MissingAssistantToolCallError(f"Message id: {message.id}")
            else:
                logging.warning(
                    f"Tool message without preceding assistant message with tool_calls: ID = {message.id}. Repairing by removing tool message"
                )
                continue
        else:
            validated_context_messages.append(message)

    return validated_context_messages


def _has_assistant_tool_call(tool_call_id: Optional[str], context_messages: List[ContextMessage]) -> bool:
    """
    Assistant tool call message must be in the most recent assistant message
    """
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
        any,
    )


@logged_exec_time
def get_relevant_memories(ctx: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    from .context import is_memory_in_context

    message_content = pipe(
        context_messages,
        remove(lambda x: x.role == SYSTEM),
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
        partial(get_embedding, ctx.embedding_model),
        lambda x: juxt(get_most_relevant_goal, get_most_relevant_memory)(ctx, x),
        filter(lambda x: x is not None),
        remove(partial(is_memory_in_context, context_messages)),
        map(
            lambda x: ContextMessage(
                role=SYSTEM,
                memory_metadata=[MemoryMetadata(memory_type=x.__class__.__name__, id=x.id, name=x.get_name())],
                content="Information recalled from assistant memory: " + x.to_fact(),
                chat_model=None,
            )
        ),
        list,
    )

    return new_memory_messages
