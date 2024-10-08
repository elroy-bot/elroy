from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, Session, SQLModel, desc, select
from toolz import first, pipe
from toolz.curried import map, pipe

from elroy.store.data_models import (Goal, MemoryMetadata, ToolCall,
                                     convert_to_utc)
from elroy.system.clock import get_utc_now
from elroy.system.parameters import CHAT_MODEL
from elroy.system.utils import first_or_none, last_or_none, logged_exec_time


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


def _get_last_user_message(session: Session, user_id: int) -> Optional[Message]:
    statement = select(Message).where(Message.user_id == user_id, Message.role == "user").order_by(desc(Message.created_at))
    return session.exec(statement).first()


def get_time_since_last_user_message(session: Session, user_id: int) -> Optional[timedelta]:
    last_user_message = _get_last_user_message(session, user_id)

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


@dataclass
class ContextMessage:
    content: Optional[str]
    role: str
    id: Optional[int] = None
    created_at_utc_epoch_secs: Optional[float] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    memory_metadata: List[MemoryMetadata] = field(default_factory=list)

    def __post_init__(self):

        if self.tool_calls is not None:
            self.tool_calls = [ToolCall(**tc) if isinstance(tc, dict) else tc for tc in self.tool_calls]
        # as per openai requirements, empty arrays are disallowed
        if self.tool_calls == []:
            self.tool_calls = None
        if self.role != "assistant" and self.tool_calls is not None:
            raise ValueError(f"Only assistant messages can have tool calls, found {self.role} message with tool calls. ID = {self.id}")
        elif self.role != "tool" and self.tool_call_id is not None:
            raise ValueError(f"Only tool messages can have tool call ids, found {self.role} message with tool call id. ID = {self.id}")
        elif self.role == "tool" and self.tool_call_id is None:
            raise ValueError(f"Tool messages must have tool call ids, found tool message without tool call id. ID = {self.id}")


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


def _get_context_messages_iter(session: Session, user_id: int) -> Iterable[ContextMessage]:
    # TODO: Cache this
    def get_message_dict(id: int) -> Dict:
        msg = session.exec(select(Message).where(Message.id == id)).first()
        assert msg
        return db_message_to_context_message_dict(msg)

    agent_context = session.exec(
        select(ContextMessageSet).where(ContextMessageSet.user_id == user_id, ContextMessageSet.is_active == True)
    ).first()

    return pipe(
        [] if not agent_context else agent_context.message_ids,
        map(get_message_dict),
        map(lambda d: ContextMessage(**d)),
        list,
    )  # type: ignore


def get_current_system_message(session: Session, user_id: int) -> Optional[ContextMessage]:
    try:
        return first(_get_context_messages_iter(session, user_id))
    except StopIteration:
        return None


def get_last_context_message(session: Session, user_id: int) -> Optional[ContextMessage]:
    try:
        return last_or_none(_get_context_messages_iter(session, user_id))
    except StopIteration:
        return None


@logged_exec_time
def get_context_messages(session: Session, user_id: int) -> List[ContextMessage]:
    return list(_get_context_messages_iter(session, user_id))


def replace_context_messages(session: Session, user_id: int, messages: List[ContextMessage]) -> None:
    msg_ids = []
    for msg in messages:
        if msg.id:
            msg_ids.append(msg.id)
        else:
            db_message = context_message_to_db_message(user_id, msg)
            session.add(db_message)
            session.commit()
            session.refresh(db_message)
            msg_ids.append(db_message.id)
    existing_context = session.exec(
        select(ContextMessageSet).where(ContextMessageSet.user_id == user_id, ContextMessageSet.is_active == True)
    ).first()

    if existing_context:
        existing_context.is_active = None
        session.add(existing_context)
    new_context = ContextMessageSet(
        user_id=user_id,
        message_ids=msg_ids,
        is_active=True,
    )
    session.add(new_context)
    session.commit()


class InvalidContextMessageError(ValueError):
    pass
