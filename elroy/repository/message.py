from dataclasses import asdict
from datetime import timedelta
from typing import Dict, Iterable, List, Optional

from sqlmodel import select
from toolz import first, pipe
from toolz.curried import filter, map, pipe

from ..config.config import ElroyContext
from ..config.constants import CHAT_MODEL
from ..repository.data_models import (
    USER,
    ContextMessage,
    ContextMessageSet,
    MemoryMetadata,
    Message,
)
from ..utils.clock import ensure_utc, get_utc_now
from ..utils.utils import last_or_none, logged_exec_time


def context_message_to_db_message(user_id: int, context_message: ContextMessage):

    return Message(
        id=context_message.id,
        user_id=user_id,
        content=context_message.content,
        role=context_message.role,
        model=CHAT_MODEL,
        tool_calls=[asdict(t) for t in context_message.tool_calls] if context_message.tool_calls else None,
        tool_call_id=context_message.tool_call_id,
        memory_metadata=[asdict(m) for m in context_message.memory_metadata],
    )


def db_message_to_context_message_dict(db_message: Message) -> Dict:
    return {
        "id": db_message.id,
        "content": db_message.content,
        "role": db_message.role,
        "created_at": ensure_utc(db_message.created_at),
        "tool_calls": db_message.tool_calls,
        "tool_call_id": db_message.tool_call_id,
        "memory_metadata": [MemoryMetadata(**m) for m in db_message.memory_metadata] if db_message.memory_metadata else [],
    }


def get_current_context_message_set_db(context: ElroyContext) -> Optional[ContextMessageSet]:
    return context.session.exec(
        select(ContextMessageSet).where(
            ContextMessageSet.user_id == context.user_id,
            ContextMessageSet.is_active == True,
        )
    ).first()


def get_time_since_context_message_creation(context: ElroyContext) -> Optional[timedelta]:
    row = get_current_context_message_set_db(context)

    if row:
        return get_utc_now() - ensure_utc(row.created_at)


def _get_context_messages_iter(context: ElroyContext) -> Iterable[ContextMessage]:
    # TODO: Cache this
    def get_message_dict(id: int) -> Dict:
        msg = context.session.exec(select(Message).where(Message.id == id)).first()
        assert msg
        return db_message_to_context_message_dict(msg)

    agent_context = get_current_context_message_set_db(context)

    return pipe(
        [] if not agent_context else agent_context.message_ids,
        map(get_message_dict),
        map(lambda d: ContextMessage(**d)),
        list,
    )  # type: ignore


def get_current_system_message(context: ElroyContext) -> Optional[ContextMessage]:
    try:
        return first(_get_context_messages_iter(context))
    except StopIteration:
        return None


@logged_exec_time
def get_time_since_most_recent_user_message(context: ElroyContext) -> Optional[timedelta]:
    return pipe(
        _get_context_messages_iter(context),
        filter(lambda x: x.role == USER),
        last_or_none,
        lambda x: get_utc_now() - x.created_at if x else None,
    )  # type: ignore


@logged_exec_time
def get_context_messages(context: ElroyContext) -> List[ContextMessage]:
    return list(_get_context_messages_iter(context))


def persist_messages(context: ElroyContext, messages: List[ContextMessage]) -> List[int]:
    msg_ids = []
    for msg in messages:
        if msg.id:
            msg_ids.append(msg.id)
        else:
            db_message = context_message_to_db_message(context.user_id, msg)
            context.session.add(db_message)
            context.session.commit()
            context.session.refresh(db_message)
            msg_ids.append(db_message.id)
    return msg_ids


def remove_context_messages(context: ElroyContext, messages: List[ContextMessage]) -> None:
    assert all(m.id is not None for m in messages), "All messages must have an id to be removed"

    msg_ids = [m.id for m in messages]

    replace_context_messages(context, [m for m in get_context_messages(context) if m.id not in msg_ids])


def add_context_messages(context: ElroyContext, messages: List[ContextMessage]) -> None:
    replace_context_messages(
        context,
        get_context_messages(context) + messages,
    )


def replace_context_messages(context: ElroyContext, messages: List[ContextMessage]) -> None:
    msg_ids = persist_messages(context, messages)

    existing_context = context.session.exec(
        select(ContextMessageSet).where(
            ContextMessageSet.user_id == context.user_id,
            ContextMessageSet.is_active == True,
        )
    ).first()

    if existing_context:
        existing_context.is_active = None
        context.session.add(existing_context)
    new_context = ContextMessageSet(
        user_id=context.user_id,
        message_ids=msg_ids,
        is_active=True,
    )
    context.session.add(new_context)
    context.session.commit()
