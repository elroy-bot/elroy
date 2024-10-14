from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel, desc, select
from toolz import first, pipe
from toolz.curried import map, pipe

from elroy.config import ElroyContext
from elroy.store.data_models import (ContextMessage, Goal, MemoryMetadata,
                                     convert_to_utc)
from elroy.system.clock import get_utc_now
from elroy.system.parameters import CHAT_MODEL
from elroy.system.utils import first_or_none, last_or_none


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="Elroy user for context")
    role: str = Field(..., description="The role of the message")
    content: Optional[str] = Field(..., description="The text of the message")
    model: Optional[str] = Field(None, description="The model used to generate the message")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(sa_column=Column(JSON))
    tool_call_id: Optional[str] = Field(None, description="The id of the tool call")
    memory_metadata: Optional[List[Dict[str, Any]]] = Field(
        sa_column=Column(JSON), description="Metadata for which memory entities are associated with this message"
    )


def _get_last_user_message(context: ElroyContext) -> Optional[Message]:
    statement = (
        select(Message)
        .where(
            Message.user_id == context.user_id,
            Message.role == "user",
        )
        .order_by(desc(Message.created_at))
    )
    return context.session.exec(statement).first()


def get_time_since_last_user_message(context: ElroyContext) -> Optional[timedelta]:
    last_user_message = _get_last_user_message(context)

    if not last_user_message:
        return None

    else:
        return get_utc_now() - convert_to_utc(last_user_message.created_at)


class ContextMessageSet(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="Elroy user for context")
    message_ids: List[int] = Field(sa_column=Column(JSON), description="The messages in the context window")
    is_active: Optional[bool] = Field(True, description="Whether the context is active")


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
        "created_at_utc_epoch_secs": db_message.created_at.timestamp(),
        "tool_calls": db_message.tool_calls,
        "tool_call_id": db_message.tool_call_id,
        "memory_metadata": [MemoryMetadata(**m) for m in db_message.memory_metadata] if db_message.memory_metadata else [],
    }


def get_message_goal_id(context_message: ContextMessage) -> Optional[int]:
    return pipe(
        [m.id for m in context_message.memory_metadata if m.memory_type == Goal.__name__],
        first_or_none,
    )  # type: ignore


def _get_context_messages_iter(context: ElroyContext) -> Iterable[ContextMessage]:
    # TODO: Cache this
    def get_message_dict(id: int) -> Dict:
        msg = context.session.exec(select(Message).where(Message.id == id)).first()
        assert msg
        return db_message_to_context_message_dict(msg)

    agent_context = context.session.exec(
        select(ContextMessageSet).where(
            ContextMessageSet.user_id == context.user_id,
            ContextMessageSet.is_active == True,
        )
    ).first()

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


def get_last_context_message(context: ElroyContext) -> Optional[ContextMessage]:
    try:
        return last_or_none(_get_context_messages_iter(context))
    except StopIteration:
        return None


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


class InvalidContextMessageError(ValueError):
    pass
