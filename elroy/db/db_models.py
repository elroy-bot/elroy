import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Column, Field, SQLModel
from toolz import pipe
from toolz.curried import filter

from ..config.constants import EMBEDDING_SIZE
from ..utils.clock import get_utc_now

USER, ASSISTANT, TOOL, SYSTEM = ["user", "assistant", "tool", "system"]


@dataclass
class ToolCall:
    """
    OpenAI formatting for tool calls
    """

    id: str
    function: Dict[str, Any]
    type: str = "function"


@dataclass
class FunctionCall:
    """
    Internal representation of a tool call, formatted for simpler execution logic
    """

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


class VectorStorage(SQLModel, table=True):
    """Table for storing vector embeddings for any model type"""

    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    source_type: str = Field(..., description="The type of model this embedding is for (e.g. Memory, Goal)")
    source_id: int = Field(..., description="The ID of the source model")
    embedding_data: List[float] = Field(
        ..., description="The vector embedding data", sa_column=Column(Vector(EMBEDDING_SIZE), nullable=False)
    )
    embedding_text_md5: str = Field(..., description="Hash of the text used to generate the embedding")


class EmbeddableSqlModel(ABC, SQLModel):
    id: Optional[int]
    created_at: datetime
    updated_at: datetime
    user_id: int
    is_active: Optional[bool]

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def to_fact(self) -> str:
        raise NotImplementedError

    def to_memory_metadata(self) -> MemoryMetadata:
        return MemoryMetadata(memory_type=self.__class__.__name__, id=self.id, name=self.get_name())  # type: ignore


EmbeddableType = TypeVar("EmbeddableType", bound=EmbeddableSqlModel)


class User(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    token: str = Field(..., description="The unique token for the user")
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)


class Memory(EmbeddableSqlModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="Elroy user for context")
    name: str = Field(..., description="The name of the context")
    text: str = Field(..., description="The text of the message")
    is_active: Optional[bool] = Field(default=True, description="Whether the context is active")

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
    status_updates: str = Field(
        sa_column=Column(Text, nullable=False, server_default="[]"),
        default="[]",
        description="Status update reports from the goal as JSON string",
    )

    def to_fact(self) -> str:
        from ..repository.goals.operations import (
            add_goal_status_update,
            mark_goal_completed,
        )

        status_updates = self.get_status_updates()

        return pipe(
            [
                f"# {self.__class__.__name__}: {self.name}",
                self.description if self.description else None,
                f"## Strategy\n{self.strategy}" if self.strategy else None,
                f"## End Condition\n{self.end_condition}" if self.end_condition else None,
                f"## Target Completion Time\n{self.target_completion_time}" if self.target_completion_time else None,
                "## Status Updates\n" + ("\n".join(status_updates) if status_updates else "No status updates"),
                f"## Priority\n{self.priority}" if self.priority else None,
                f"### Note for assistant:\nInformation about this goal should be kept up to date via AI assistant functions: {add_goal_status_update.__name__}, and {mark_goal_completed.__name__}",
            ],
            filter(lambda x: x is not None),
            "\n\n".join,
        )  # type: ignore

    def get_status_updates(self) -> List[str]:
        """Get deserialized status updates"""
        return json.loads(self.status_updates)

    def set_status_updates(self, updates: List[str]) -> None:
        """Set status updates with JSON serialization"""
        self.status_updates = json.dumps(updates)

    description: Optional[str] = Field(..., description="The description of the goal")
    strategy: Optional[str] = Field(..., description="The strategy to achieve the goal")
    end_condition: Optional[str] = Field(..., description="The condition that will end the goal")
    is_active: Optional[bool] = Field(default=True, description="Whether the goal is complete")
    priority: Optional[int] = Field(4, description="The priority of the goal")
    target_completion_time: Optional[datetime] = Field(default=None, description="The datetime of the targeted completion for the goal.")

    def get_name(self) -> str:
        return self.name


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="Elroy user for context")
    role: str = Field(..., description="The role of the message")
    content: Optional[str] = Field(..., description="The text of the message")
    model: Optional[str] = Field(None, description="The model used to generate the message")
    tool_calls: Optional[str] = Field(sa_column=Column(Text), description="Tool calls as JSON string")
    tool_call_id: Optional[str] = Field(None, description="The id of the tool call")
    memory_metadata: Optional[str] = Field(sa_column=Column(Text), description="Metadata for which memory entities as JSON string")

    def get_tool_calls(self) -> Optional[List[Dict[str, Any]]]:
        """Get deserialized tool calls"""
        if self.tool_calls is None:
            return None
        return json.loads(self.tool_calls)

    def set_tool_calls(self, tool_calls: Optional[List[Dict[str, Any]]]) -> None:
        """Set tool calls with JSON serialization"""
        if tool_calls is None:
            self.tool_calls = None
        else:
            self.tool_calls = json.dumps(tool_calls)

    def get_memory_metadata(self) -> Optional[List[Dict[str, Any]]]:
        """Get deserialized memory metadata"""
        if self.memory_metadata is None:
            return None
        return json.loads(self.memory_metadata)

    def set_memory_metadata(self, metadata: Optional[List[Dict[str, Any]]]) -> None:
        """Set memory metadata with JSON serialization"""
        if metadata is None:
            self.memory_metadata = None
        else:
            self.memory_metadata = json.dumps(metadata)


class UserPreference(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="User for context")
    preferred_name: Optional[str] = Field(default=None, description="The preferred name for the user")
    system_persona: Optional[str] = Field(
        default=None, description="The system persona for the user, included in the system instruction. If unset, a default is used"
    )
    full_name: Optional[str] = Field(default=None, description="The full name for the user")
    is_active: Optional[bool] = Field(default=True, description="Whether the context is active")
    assistant_name: Optional[str] = Field(default=None, description="The assistant name for the user")


class ContextMessageSet(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="Elroy user for context")
    message_ids: str = Field(sa_column=Column(Text), description="The messages in the context window as JSON string")

    def get_message_ids(self) -> List[int]:
        """Get deserialized message IDs"""
        return json.loads(self.message_ids)

    def set_message_ids(self, ids: List[int]) -> None:
        """Set message IDs with JSON serialization"""
        self.message_ids = json.dumps(ids)

    is_active: Optional[bool] = Field(True, description="Whether the context is active")
