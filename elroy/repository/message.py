import json
from dataclasses import asdict
from datetime import timedelta
from functools import partial
from typing import Iterable, List, Optional, Union

from sqlmodel import select
from toolz import first, pipe
from toolz.curried import filter, map, pipe

from ..config.constants import SYSTEM_INSTRUCTION_LABEL
from ..config.ctx import ElroyContext
from ..db.db_models import (
    SYSTEM,
    USER,
    ContextMessageSet,
    MemoryMetadata,
    Message,
    ToolCall,
)
from ..utils.clock import ensure_utc, get_utc_now
from ..utils.utils import last_or_none, logged_exec_time
from .data_models import ContextMessage


# This is hacky, should add arbitrary metadata
def is_system_instruction(message: Optional[ContextMessage]) -> bool:
    return (
        message is not None
        and message.content is not None
        and message.content.startswith(SYSTEM_INSTRUCTION_LABEL)
        and message.role == SYSTEM
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
            map(lambda x: MemoryMetadata(**x)),
            list,
        ),
    )


def get_current_context_message_set_db(ctx: ElroyContext) -> Optional[ContextMessageSet]:
    return ctx.db.exec(
        select(ContextMessageSet).where(
            ContextMessageSet.user_id == ctx.user_id,
            ContextMessageSet.is_active == True,
        )
    ).first()


def get_time_since_context_message_creation(ctx: ElroyContext) -> Optional[timedelta]:
    row = get_current_context_message_set_db(ctx)

    if row:
        return get_utc_now() - ensure_utc(row.created_at)


def _get_context_messages_iter(ctx: ElroyContext) -> Iterable[ContextMessage]:
    """
    Gets context messages from db, in order of their position in ContextMessageSet
    """

    message_ids = pipe(
        get_current_context_message_set_db(ctx),
        lambda x: x.message_ids if x else "[]",
        json.loads,
    )

    assert isinstance(message_ids, list)

    return pipe(
        ctx.db.exec(select(Message).where(Message.id.in_(message_ids))),  # type: ignore
        lambda messages: sorted(messages, key=lambda m: message_ids.index(m.id)),
        map(db_message_to_context_message),
    )  # type: ignore


def get_current_system_message(ctx: ElroyContext) -> Optional[ContextMessage]:
    try:
        return first(_get_context_messages_iter(ctx))
    except StopIteration:
        return None


@logged_exec_time
def get_time_since_most_recent_user_message(context_messages: Iterable[ContextMessage]) -> Optional[timedelta]:
    return pipe(
        context_messages,
        filter(lambda x: x.role == USER),
        last_or_none,
        lambda x: get_utc_now() - x.created_at if x else None,
    )  # type: ignore


@logged_exec_time
def get_context_messages(ctx: ElroyContext) -> List[ContextMessage]:
    return list(_get_context_messages_iter(ctx))


def persist_messages(ctx: ElroyContext, messages: List[ContextMessage]) -> List[int]:
    msg_ids = []
    for msg in messages:
        if msg.id:
            msg_ids.append(msg.id)
        else:
            db_message = context_message_to_db_message(ctx.user_id, msg)
            ctx.db.add(db_message)
            ctx.db.commit()
            ctx.db.refresh(db_message)
            msg_ids.append(db_message.id)
    return msg_ids


def remove_context_messages(ctx: ElroyContext, messages: List[ContextMessage]) -> None:
    assert all(m.id is not None for m in messages), "All messages must have an id to be removed"

    msg_ids = [m.id for m in messages]

    replace_context_messages(ctx, [m for m in get_context_messages(ctx) if m.id not in msg_ids])


def add_context_messages(ctx: ElroyContext, messages: Union[ContextMessage, List[ContextMessage]]) -> None:
    pipe(
        messages,
        lambda x: x if isinstance(x, List) else [x],
        lambda x: get_context_messages(ctx) + x,
        partial(replace_context_messages, ctx),
    )


def replace_context_messages(ctx: ElroyContext, messages: List[ContextMessage]) -> None:
    msg_ids = persist_messages(ctx, messages)

    existing_context = ctx.db.exec(
        select(ContextMessageSet).where(
            ContextMessageSet.user_id == ctx.user_id,
            ContextMessageSet.is_active == True,
        )
    ).first()

    if existing_context:
        existing_context.is_active = None
        ctx.db.add(existing_context)
    new_context = ContextMessageSet(
        user_id=ctx.user_id,
        message_ids=json.dumps(msg_ids),
        is_active=True,
    )
    ctx.db.add(new_context)
    ctx.db.commit()
