import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from pgvector.sqlalchemy import Vector
from pydantic import BaseModel
from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Column, Field, SQLModel
from toolz import pipe
from toolz.curried import filter

from ..core.constants import EMBEDDING_SIZE, RecoverableToolError
from ..utils.clock import utc_now


@dataclass
class ToolCall:
    """
    OpenAI formatting for tool calls
    """

    id: str
    function: Dict[str, Any]
    type: str = "function"

    def to_json(self) -> Dict[str, Any]:
        return {"id": self.id, "function": self.function, "type": self.type}


class FunctionCall(BaseModel):
    """
    Internal representation of a tool call, formatted for simpler execution logic
    """

    # Formatted for ease of execution
    id: str
    function_name: str
    arguments: Dict

    def __str__(self):
        return json.dumps({self.function_name: self.arguments})

    def to_tool_call(self) -> ToolCall:
        return ToolCall(id=self.id, function={"name": self.function_name, "arguments": json.dumps(self.arguments)})


class VectorStorage(SQLModel, table=True):
    """Table for storing vector embeddings for any model type"""

    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    source_type: str = Field(..., description="The type of model this embedding is for (e.g. Memory, Goal)")
    source_id: int = Field(..., description="The ID of the source model")
    user_id: int = Field(..., description="The user ID for the vector")
    embedding_data: List[float] = Field(
        ..., description="The vector embedding data", sa_column=Column(Vector(EMBEDDING_SIZE), nullable=False)
    )
    embedding_text_md5: str = Field(..., description="Hash of the text used to generate the embedding")


class MemorySource(ABC):
    """Abstract base class for memory sources"""

    id: Optional[int]
    user_id: int

    @abstractmethod
    def get_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def to_fact(self) -> str:
        raise NotImplementedError

    @classmethod
    def source_type(cls) -> str:
        return cls.__name__

    def to_memory_source_d(self) -> Dict[str, Any]:
        return {"source_type": self.source_type(), "id": self.id}


class EmbeddableSqlModel(ABC, SQLModel):
    id: Optional[int]
    user_id: int
    is_active: Optional[bool]

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def to_fact(self) -> str:
        raise NotImplementedError


class User(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(..., description="The unique token for the user")
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)  # noqa F841


class Memory(EmbeddableSqlModel, MemorySource, SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)  # noqa F841
    user_id: int = Field(..., description="Elroy user for context")
    name: str = Field(..., description="The name of the context")
    text: str = Field(..., description="The text of the message")
    source_metadata: str = Field(sa_column=Column(Text), default="[]", description="Metadata for the memory as JSON string")
    is_active: Optional[bool] = Field(default=True, description="Whether the context is active")

    def get_name(self) -> str:
        return self.name

    def to_fact(self) -> str:
        return f"#{self.name}\n{self.text}"


class Reminder(EmbeddableSqlModel, MemorySource, SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "name", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)  # noqa F841
    user_id: int = Field(..., description="Elroy user for context")
    name: str = Field(..., description="The name of the reminder")
    text: str = Field(..., description="The text of the reminder")
    trigger_datetime: Optional[datetime] = Field(default=None, description="When the reminder should trigger (for timed reminders)")
    reminder_context: Optional[str] = Field(default=None, description="When the reminder should be triggered (for contextual reminders)")
    is_active: Optional[bool] = Field(default=True, description="Whether the reminder is active")
    is_recurring: Optional[bool] = Field(default=False, description="Whether the reminder is recurring (for contextual reminders)")

    def get_name(self) -> str:
        return self.name

    def to_fact(self) -> str:
        if self.trigger_datetime:
            return f"#{self.name} (Timed: {self.trigger_datetime.strftime('%Y-%m-%d %H:%M:%S')})\n{self.text}"
        elif self.reminder_context:
            recurring_text = " (Recurring)" if self.is_recurring else ""
            return f"#{self.name} (Context: {self.reminder_context}){recurring_text}\n{self.text}"
        else:
            return f"#{self.name}\n{self.text}"


class SourceDocument(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "address"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)  # noqa F841
    user_id: int = Field(..., description="Elroy user for context")
    address: str = Field(..., description="The address of the document")
    name: str = Field(..., description="The name of the document")
    content: Optional[str] = Field(..., description="The extracted content of the document")
    extracted_at: datetime = Field(default_factory=utc_now, nullable=False)  # noqa F841
    content_md5: Optional[str] = Field(..., description="The MD5 hash of the extracted content")


class DocumentExcerpt(EmbeddableSqlModel, MemorySource, table=True):
    __table_args__ = (UniqueConstraint("user_id", "source_document_id", "chunk_index", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)  # noqa F841
    user_id: int = Field(..., description="Elroy user for context")
    name: str = Field(..., description="The name of the document")
    content: str = Field(..., description="The text of the document")
    source_document_id: int = Field(..., description="The source document ID")
    chunk_index: int = Field(..., description="The index of the chunk in the source document")
    content_md5: str = Field(..., description="The MD5 hash of the text")
    is_active: Optional[bool] = Field(default=True, description="Whether the context is active")

    def get_name(self) -> str:
        return self.name

    def to_fact(self) -> str:
        return f"#{self.name}\n{self.content}"


class Goal(EmbeddableSqlModel, MemorySource, SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "name", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)  # noqa F841
    user_id: int = Field(..., description="Elroy user whose assistant is being reminded")
    name: str = Field(..., description="The name of the goal")
    status_updates: str = Field(
        sa_column=Column(Text, nullable=False, server_default="[]"),
        default="[]",
        description="Status update reports from the goal as JSON string",
    )

    def to_fact(self) -> str:
        from ..repository.goals.tools import add_goal_status_update, mark_goal_completed

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


class MemoryOperationTracker(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(..., description="User associated with the memory operations")
    memories_since_consolidation: int = Field(
        default=0, description="Number of new memories created since the last consolidation operation"
    )
    messages_since_memory: int = Field(default=0, description="Number of messages processed since the last memory creation")
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)  # noqa F841


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)  # noqa F841
    user_id: int = Field(..., description="Elroy user for context")
    role: str = Field(..., description="The role of the message")
    content: Optional[str] = Field(..., description="The text of the message")
    model: Optional[str] = Field(None, description="The model used to generate the message")
    tool_calls: Optional[str] = Field(sa_column=Column(Text), description="Tool calls as JSON string")
    tool_call_id: Optional[str] = Field(None, description="The id of the tool call")
    memory_metadata: Optional[str] = Field(sa_column=Column(Text), description="Metadata for which memory entities as JSON string")


class UserPreference(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)  # noqa F841
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
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)  # noqa F841
    user_id: int = Field(..., description="Elroy user for context")
    message_ids: str = Field(sa_column=Column(Text), description="The messages in the context window as JSON string")
    is_active: Optional[bool] = Field(True, description="Whether the context is active")


def get_mem_source_options() -> Dict[str, Type[MemorySource]]:
    # Note, this is brittle! Should be replaced in the future with a registration process.
    from ..repository.context_messages.transforms import ContextMessageSetWithMessages

    return {source_class.source_type(): source_class for source_class in MemorySource.__subclasses__() + [ContextMessageSetWithMessages]}


class InvalidMemorySourceTypeError(RecoverableToolError):
    def __init__(self, source_type: str):
        super().__init__(f"Invalid memory source type: {source_type}. Valid options are: {get_mem_source_options().keys()}")


def get_memory_source_class(source_type: str) -> Type[MemorySource]:

    options = get_mem_source_options()

    if source_type in options:
        return options[source_type]
    else:
        raise InvalidMemorySourceTypeError(source_type)
