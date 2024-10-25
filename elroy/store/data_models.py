import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz
from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Column, Field, SQLModel

from elroy.system.clock import get_utc_now
from elroy.system.parameters import EMBEDDING_SIZE


USER, ASSISTANT, TOOL, SYSTEM = VALID_CONTEXT_MESSAGE_ROLES = ["user", "assistant", "tool", "system"]


@dataclass
class ToolCall:
    # formatted for openai
    id: str
    function: Dict[str, Any]
    type: str = "function"


@dataclass
class FunctionCall:
    # Formatted for ease of execution
    id: str
    function_name: str
    arguments: Dict

    def to_tool_call(self) -> ToolCall:
        return ToolCall(id=self.id, function={"name": self.function_name, "arguments": json.dumps(self.arguments)})


@dataclass
class MemoryMetadata:
    memory_type: str
    id: int
    name: str


class EmbeddableSqlModel(ABC, SQLModel):
    id: Optional[int]
    created_at: datetime
    updated_at: datetime
    user_id: int
    is_active: Optional[bool]
    embedding: Optional[List[float]] = Field(sa_column=Column(Vector(EMBEDDING_SIZE)))
    embedding_text_md5: Optional[str] = Field(..., description="Hash of the text used to generate the embedding")

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def to_fact(self) -> str:
        pass

    def to_memory_metadata(self) -> MemoryMetadata:
        return MemoryMetadata(memory_type=self.__class__.__name__, id=self.id, name=self.get_name())  # type: ignore


class User(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)


def convert_to_utc(dt: datetime) -> datetime:
    """Convert a datetime object to UTC if it contains time; leave date-only as naive."""
    if dt.tzinfo is None:
        return pytz.utc.localize(dt)
    else:
        return dt.astimezone(pytz.UTC)


class Memory(EmbeddableSqlModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="Elroy user for context")
    name: str = Field(..., description="The name of the context")
    text: str = Field(..., description="The text of the message")
    is_active: Optional[bool] = Field(default=True, description="Whether the context is active")
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(EMBEDDING_SIZE)))
    embedding_text_md5: Optional[str] = Field(default=None, description="Hash of the text used to generate the embedding")

    def get_name(self) -> str:
        return self.name

    def to_fact(self) -> str:
        return f"#{self.name}\n{self.text}"


class Goal(EmbeddableSqlModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "name", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="Elroy user whose assistant is being reminded")
    name: str = Field(..., description="The name of the goal")
    description: str = Field(..., description="The description of the goal")
    status_updates: List[str] = Field(
        sa_column=Column(JSON, nullable=False, server_default="[]"),
        default_factory=list,
        description="Status update reports from the goal",
    )
    strategy: str = Field(..., description="The strategy to achieve the goal")
    end_condition: str = Field(..., description="The condition that will end the goal")
    is_active: Optional[bool] = Field(default=True, description="Whether the goal is complete")
    priority: Optional[int] = Field(4, description="The priority of the goal")
    target_completion_time: Optional[datetime] = Field(default=None, description="The datetime of the targeted completion for the goal.")
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(EMBEDDING_SIZE)))
    embedding_text_md5: Optional[str] = Field(default=None, description="Hash of the text used to generate the embedding")

    def get_name(self) -> str:
        return self.name

    def to_fact(self) -> str:
        from elroy.store.goals import (add_goal_status_update,
                                       mark_goal_completed)

        return "\n\n".join(
            [
                f"# {self.__class__.__name__}: {self.name}",
                self.description,
                f"## Strategy\n{self.strategy}",
                f"## End Condition\n{self.end_condition}",
                f"## Target Completion Time\n{self.target_completion_time}",
                "## Status Updates\n" + ("\n".join(self.status_updates) if self.status_updates else "No status updates"),
                f"## Priority\n{self.priority}",
                f"### Note for assistant:\nInformation about this goal should be kept up to date via AI assistant functions: {add_goal_status_update.__name__}, and {mark_goal_completed.__name__}",
            ]
        )


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
        if self.role != ASSISTANT and self.tool_calls is not None:
            raise ValueError(f"Only assistant messages can have tool calls, found {self.role} message with tool calls. ID = {self.id}")
        elif self.role != TOOL and self.tool_call_id is not None:
            raise ValueError(f"Only tool messages can have tool call ids, found {self.role} message with tool call id. ID = {self.id}")
        elif self.role == TOOL and self.tool_call_id is None:
            raise ValueError(f"Tool messages must have tool call ids, found tool message without tool call id. ID = {self.id}")


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


class UserPreference(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="User for context")
    preferred_name: Optional[str] = Field(default=None, description="The preferred name for the user")
    full_name: Optional[str] = Field(default=None, description="The full name for the user")
    is_active: Optional[bool] = Field(default=True, description="Whether the context is active")


class ContextMessageSet(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="Elroy user for context")
    message_ids: List[int] = Field(sa_column=Column(JSON), description="The messages in the context window")
    is_active: Optional[bool] = Field(True, description="Whether the context is active")
