# This is hacky, should add arbitrary metadata
import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from datetime import timedelta
from functools import partial, reduce
from operator import add

from sqlmodel import Session, col, select
from toolz import concat, pipe
from toolz.curried import filter, map, remove

from ...core.constants import ASSISTANT, SYSTEM, SYSTEM_INSTRUCTION_LABEL, TOOL, USER
from ...core.logging import get_logger
from ...db.db_models import ContextMessageSet, MemorySource, Message, ToolCall
from ...llm.utils import count_tokens
from ...utils.clock import ensure_utc, utc_now
from ...utils.utils import datetime_to_string, last_or_none
from ..user.queries import do_get_assistant_name, do_get_user_preferred_name
from .data_models import ContextMessage

logger = get_logger()


def is_system_instruction(message: ContextMessage | None) -> bool:
    return (
        message is not None
        and message.content is not None
        and message.content.startswith(SYSTEM_INSTRUCTION_LABEL)
        and message.role == SYSTEM
    )


def get_time_since_most_recent_user_message(context_messages: Iterable[ContextMessage]) -> timedelta | None:
    return pipe(
        context_messages,
        filter(lambda x: x.role == USER),
        last_or_none,
        lambda x: (utc_now() - x.created_at) if x and x.created_at else None,
    )


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
    )


def context_message_to_db_message(user_id: int, context_message: ContextMessage):

    return Message(
        id=context_message.id,
        created_at=context_message.created_at,
        user_id=user_id,
        content=context_message.content,
        role=context_message.role,
        model=context_message.chat_model,
        tool_calls=json.dumps([asdict(t) for t in context_message.tool_calls]) if context_message.tool_calls else None,
        tool_call_id=context_message.tool_call_id,
    )


def is_context_refresh_needed(context_messages: Iterable[ContextMessage], chat_model_name: str, max_tokens: int) -> bool:

    if sum(1 for m in context_messages if m.role == USER) == 0:
        logger.info("No user messages in context, no context refresh needed")
        return False

    token_count = pipe(
        context_messages,
        remove(lambda _: _.content is None),
        map(partial(count_tokens, chat_model_name)),
        lambda seq: reduce(add, seq, 0),
    )
    assert isinstance(token_count, int)

    if token_count > max_tokens:
        logger.info(f"Token count {token_count} exceeds threshold {max_tokens}")
        return True
    else:
        logger.info(f"Token count {token_count} does not exceed threshold {max_tokens}")
        return False


def format_message(
    message: ContextMessage,
    user_preferred_name: str | None,
    assistant_name: str | None,
) -> list[str]:
    datetime_str = datetime_to_string(message.created_at)
    if message.role == SYSTEM:
        return [f"SYSTEM ({datetime_str}): {message.content}"]
    elif message.role == USER:
        user_name = user_preferred_name.upper() if user_preferred_name else "USER"

        return [f"{user_name} ({datetime_str}): {message.content}"]
    elif message.role == ASSISTANT:
        msgs = []

        if message.content:
            msgs.append(f"{assistant_name} ({datetime_str}): {message.content}")
        if message.tool_calls:
            pipe(
                message.tool_calls,
                map(lambda x: x.function),
                map(
                    lambda x: (
                        f"{assistant_name} TOOL CALL REQUEST ({datetime_str}): function name: {x['name']}, arguments: {x['arguments']}"
                    )
                ),
                list,
                msgs.extend,
            )
        if not message.content and not message.tool_calls:
            raise ValueError(f"Expected either message text or tool call: {message}")
        return msgs
    elif message.role == TOOL:
        return [f"TOOL CALL RESULT ({datetime_str}): {message.content}"]
    else:
        logger.warning(f"Cannot format message: {message}")
        return []


def format_context_messages(
    context_messages: Iterable[ContextMessage],
    user_preferred_name: str,
    assistant_name: str,
) -> str:
    convo_range = pipe(
        context_messages,
        filter(lambda x: x.role == USER),
        map(lambda x: x.created_at),
        filter(lambda x: x is not None),
        list,
        lambda timestamps: (
            f"Messages from {datetime_to_string(min(timestamps))} to {datetime_to_string(max(timestamps))}"
            if timestamps
            else "No messages in context"
        ),
    )

    return pipe(
        context_messages,
        filter(lambda _: _.content is not None),
        map(lambda msg: format_message(msg, user_preferred_name, assistant_name)),
        concat,
        list,
        lambda x: ["Conversation Summary"] + x + [convo_range],
        "\n\n".join,
    )


def compress_context_messages(
    chat_model_name: str,
    context_refresh_target_tokens: int,
    max_in_context_message_age: timedelta,
    context_messages: list[ContextMessage],
) -> list[ContextMessage]:
    """
    Cache-friendly compression: preserves message order, only drops old messages from the beginning.

    Strategy:
    1. Keep system message at position 0 (never changes)
    2. Scan backward from newest messages to find what fits in token budget
    3. Find cutoff index and return [system_message] + messages[cutoff_idx:]
    4. This ensures messages are never reordered, maximizing prompt cache hits
    """
    if not context_messages:
        return []

    system_message = context_messages[0]
    assert is_system_instruction(system_message)

    prev_messages = context_messages[1:]
    if not prev_messages:
        return [system_message]

    assert not any(is_system_instruction(msg) for msg in prev_messages)

    # Calculate token budget
    system_tokens = count_tokens(chat_model_name, system_message)
    remaining_budget = context_refresh_target_tokens - system_tokens

    # Find cutoff: scan backward from newest, accumulate tokens until we hit budget or age limit
    cutoff_idx = 0
    current_token_count = 0
    now = utc_now()

    # Scan in reverse (newest first) to find what fits in budget
    for idx in range(len(prev_messages) - 1, -1, -1):
        msg = prev_messages[idx]
        msg_tokens = count_tokens(chat_model_name, msg)

        # Special handling for TOOL messages: must keep with their preceding ASSISTANT message
        if idx < len(prev_messages) - 1 and prev_messages[idx + 1].role == TOOL:
            # This is an ASSISTANT message followed by TOOL result
            # We need to keep both or neither
            next_msg_tokens = count_tokens(chat_model_name, prev_messages[idx + 1])
            if current_token_count + msg_tokens + next_msg_tokens <= remaining_budget:
                # Can fit both, they're already counted/will be counted
                current_token_count += msg_tokens
                continue
            else:
                # Can't fit the pair, set cutoff after them
                cutoff_idx = idx + 2
                break

        # Check token budget
        if current_token_count + msg_tokens > remaining_budget:
            cutoff_idx = idx + 1
            break

        # Check age
        if msg.created_at and msg.created_at < now - max_in_context_message_age:
            logger.info(f"Dropping old message {msg.id}")
            cutoff_idx = idx + 1
            break

        current_token_count += msg_tokens

    # Return system message + kept messages (preserves exact order)
    kept_messages = prev_messages[cutoff_idx:]

    logger.info(f"Compression: kept {len(kept_messages)}/{len(prev_messages)} messages, {current_token_count}/{remaining_budget} tokens")

    return [system_message] + kept_messages


class ContextMessageSetWithMessages(MemorySource):
    _context_message_set: ContextMessageSet | None
    _messages: list[ContextMessage] | None
    user_id: int

    @classmethod
    def from_context_message_set(cls, session: Session, context_message_set: ContextMessageSet) -> "ContextMessageSetWithMessages":
        assert context_message_set.id
        return cls(session=session, id=context_message_set.id, user_id=context_message_set.user_id, context_message_set=context_message_set)

    def __init__(self, session: Session, id: int, user_id: int, context_message_set: ContextMessageSet | None = None):
        self._context_message_set = context_message_set
        self.session = session
        self.user_id = user_id
        self.id = id
        self._messages = None

    def get_name(self) -> str:
        return str(self.id)

    @classmethod
    def source_type(cls) -> str:
        return ContextMessageSet.__name__

    @property
    def context_message_set(self) -> ContextMessageSet:
        if self._context_message_set is not None:
            return self._context_message_set
        else:
            self._context_message_set = self.session.exec(
                select(ContextMessageSet).where(
                    ContextMessageSet.id == self.id,
                    ContextMessageSet.user_id == self.user_id,
                )
            ).first()
            if not self._context_message_set:
                raise ValueError(f"Context message set not found for ID {self.id}")
            else:
                return self._context_message_set

    def to_fact(self) -> str:
        return format_context_messages(
            self.messages_list,
            do_get_user_preferred_name(self.session, self.user_id),
            do_get_assistant_name(self.session, self.user_id),
        )

    @property
    def messages(self) -> Iterator[ContextMessage]:
        if self._messages:
            return iter(self._messages)
        else:
            message_ids = json.loads(self.context_message_set.message_ids)
            msgs = self.session.exec(select(Message).where(col(Message.id).in_(message_ids)))

            # Create a mapping of id to position
            id_to_pos = {id: pos for pos, id in enumerate(message_ids)}

            # Convert to list and sort by original position
            full_list = []
            for msg in msgs:
                ctx_msg = db_message_to_context_message(msg)
                full_list.append(ctx_msg)

            # Sort based on position in message_ids
            full_list.sort(key=lambda msg: id_to_pos[msg.id])

            self._messages = full_list
            yield from full_list

    @property
    def messages_list(self) -> list[ContextMessage]:
        if self._messages:
            return self._messages
        else:
            return list(self.messages)
