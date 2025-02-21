# This is hacky, should add arbitrary metadata
import json
import logging
from collections import deque
from dataclasses import asdict
from datetime import datetime, timedelta
from functools import partial, reduce
from operator import add
from typing import Iterable, List, Optional, Sequence

from toolz import concat, pipe
from toolz.curried import filter, map, pipe, remove

from ...config.constants import ASSISTANT, SYSTEM, SYSTEM_INSTRUCTION_LABEL, TOOL, USER
from ...db.db_models import Message, ToolCall
from ...llm.utils import count_tokens
from ...utils.clock import ensure_utc, get_utc_now
from ...utils.utils import datetime_to_string, last_or_none
from .data_models import ContextMessage, RecalledMemoryMetadata


def is_system_instruction(message: Optional[ContextMessage]) -> bool:
    return (
        message is not None
        and message.content is not None
        and message.content.startswith(SYSTEM_INSTRUCTION_LABEL)
        and message.role == SYSTEM
    )


def get_time_since_most_recent_user_message(context_messages: Iterable[ContextMessage]) -> Optional[timedelta]:
    return pipe(
        context_messages,
        filter(lambda x: x.role == USER),
        last_or_none,
        lambda x: (get_utc_now() - x.created_at) if x else None,
    )  # type: ignore


def db_message_to_context_message(db_message: Message) -> ContextMessage:
    return ContextMessage(
        id=db_message.id,
        content=db_message.content,
        role=db_message.role,
        created_at=ensure_utc(db_message.created_at),
        tool_calls=pipe(
            json.loads(db_message.tool_calls or "[]") or [],
            map(lambda x: ToolCall(**x)),
            list,
        ),
        tool_call_id=db_message.tool_call_id,
        chat_model=db_message.model,
        memory_metadata=pipe(
            json.loads(db_message.memory_metadata or "[]") or [],
            map(lambda x: RecalledMemoryMetadata(**x)),
            list,
        ),
    )


def context_message_to_db_message(user_id: int, context_message: ContextMessage):

    return Message(
        id=context_message.id,
        user_id=user_id,
        content=context_message.content,
        role=context_message.role,
        model=context_message.chat_model,
        tool_calls=json.dumps([asdict(t) for t in context_message.tool_calls]) if context_message.tool_calls else None,
        tool_call_id=context_message.tool_call_id,
        memory_metadata=json.dumps([asdict(m) for m in context_message.memory_metadata]),
    )


def is_context_refresh_needed(context_messages: List[ContextMessage], chat_model_name: str, max_tokens: int) -> bool:

    if sum(1 for m in context_messages if m.role == USER) == 0:
        logging.info("No user messages in context, no context refresh needed")
        return False

    token_count = pipe(
        context_messages,
        remove(lambda _: _.content is None),
        map(partial(count_tokens, chat_model_name)),
        lambda seq: reduce(add, seq, 0),
    )
    assert isinstance(token_count, int)

    if token_count > max_tokens:
        logging.info(f"Token count {token_count} exceeds threshold {max_tokens}")
        return True
    else:
        logging.info(f"Token count {token_count} does not exceed threshold {max_tokens}")
        return False


def replace_system_instruction(context_messages: List[ContextMessage], new_system_message: ContextMessage) -> List[ContextMessage]:
    """
    Note that this removes any prior system instruction messages, even if they are not in first position
    """
    return pipe(
        context_messages,
        remove(is_system_instruction),
        list,
        lambda x: [new_system_message] + x,
    )


def format_message(message: ContextMessage, user_preferred_name: Optional[str]) -> List[str]:
    datetime_str = datetime_to_string(message.created_at)
    if message.role == SYSTEM:
        return [f"SYSTEM ({datetime_str}): {message.content}"]
    elif message.role == USER:
        user_name = user_preferred_name.upper() if user_preferred_name else "USER"

        return [f"{user_name} ({datetime_str}): {message.content}"]
    elif message.role == ASSISTANT:
        msgs = []

        if message.content:
            msgs.append(f"ELROY ({datetime_str}): {message.content}")
        if message.tool_calls:
            pipe(
                message.tool_calls,
                map(lambda x: x.function),
                map(lambda x: f"ELROY TOOL CALL REQUEST ({datetime_str}): function name: {x['name']}, arguments: {x['arguments']}"),
                list,
                msgs.extend,
            )
        if not message.content and not message.tool_calls:
            raise ValueError(f"Expected either message text or tool call: {message}")
        return msgs
    elif message.role == TOOL:
        return [f"TOOL CALL RESULT ({datetime_str}): {message.content}"]
    else:
        logging.warning(f"Cannot format message: {message}")
        return []


def format_context_messages(context_messages: Sequence[ContextMessage], user_preferred_name: Optional[str]) -> str:
    convo_range = pipe(
        context_messages,
        filter(lambda _: _.role == USER),
        map(lambda _: _.created_at),
        list,
        lambda l: f"Messages from {datetime_to_string(min(l))} to {datetime_to_string(max(l))}" if l else "No messages in context",
    )

    return (
        pipe(
            context_messages,
            filter(
                lambda _: _.content or _.tool_calls or _.role != ASSISTANT
            ),  # TODO: Determine why these messages are making it into context
            map(lambda msg: format_message(msg, user_preferred_name)),
            concat,
            list,
            "\n".join,
            str,
        )
        + convo_range
    )  # type: ignore


def compress_context_messages(
    chat_model_name: str,
    context_refresh_target_tokens: int,
    max_in_context_message_age: timedelta,
    context_messages: List[ContextMessage],
) -> List[ContextMessage]:
    """
    Compresses messages in the context window by summarizing old messages, while keeping new messages intact.
    """
    system_message, prev_messages = context_messages[0], context_messages[1:]

    assert is_system_instruction(system_message)
    assert not any(is_system_instruction(msg) for msg in prev_messages)

    current_token_count = count_tokens(chat_model_name, system_message)

    kept_messages = deque()

    # iterate through non-system context messages in reverse order
    # we keep the most current messages that are fresh enough to be relevant
    for msg in reversed(prev_messages):  # iterate in reverse order
        msg_created_at = msg.created_at
        assert isinstance(msg_created_at, datetime)

        candidate_message_count = count_tokens(chat_model_name, msg)

        if len(kept_messages) > 0 and kept_messages[0].role == TOOL:
            # if the last message kept was a tool call, we must keep the corresponding assistant message that came before it.
            kept_messages.appendleft(msg)
            current_token_count += candidate_message_count
            continue

        if current_token_count > context_refresh_target_tokens:
            break
        elif msg_created_at < get_utc_now() - max_in_context_message_age:
            logging.info(f"Dropping old message {msg.id}")
            continue
        else:
            kept_messages.appendleft(msg)
            current_token_count += candidate_message_count

    # Keep system message first, but reverse the rest to maintain chronological order
    return [system_message] + list(kept_messages)
