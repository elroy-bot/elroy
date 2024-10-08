import enum
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz
from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Column, String, UniqueConstraint
from sqlmodel import Column, Field, SQLModel

from elroy.system.clock import get_utc_now
from elroy.system.parameters import EMBEDDING_SIZE


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
class Fact:
    name: str
    user_id: int
    text: str
    timestamp: datetime

    def __str__(self) -> str:
        return f"{self.name}\n\n{self.text}"


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
    embedding: Optional[List[float]] = Field(sa_column=Column(Vector(EMBEDDING_SIZE)))
    embedding_text_md5: Optional[str] = Field(..., description="Hash of the text used to generate the embedding")

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def to_fact(self) -> Fact:
        pass

    def to_memory_metadata(self) -> MemoryMetadata:
        return MemoryMetadata(memory_type=self.__class__.__name__, id=self.id, name=self.get_name())  # type: ignore


class User(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)


class MemoryEntity(EmbeddableSqlModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "entity_name", "entity_label"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="User whose assistant is being reminded")
    entity_name: str = Field(..., description="The name of the entity")
    entity_label: str = Field(..., description="The label of the entity")
    text: str = Field(..., description="The text of the entity")
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(EMBEDDING_SIZE)))
    embedding_text_md5: Optional[str] = Field(default=None, description="Hash of the text used to generate the embedding")

    def get_name(self) -> str:
        return f"{self.entity_label}: {self.entity_name}"

    def to_fact(self) -> Fact:
        return Fact(
            name=f"Entity: {self.entity_name} ({self.entity_label})",
            user_id=self.user_id,
            text="Memory Entity" + "\n" + self.text,
            timestamp=convert_to_utc(self.created_at),
        )


class CalendarEventDB(SQLModel, table=True):
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    user_id: int
    event_id: str
    summary: str
    description: Optional[str]
    start: datetime
    end: datetime
    location: Optional[str]
    attendee_emails: str  # csv
    recurrence: str  # csv
    reminders: bool
    visibility: str
    UniqueConstraint("event_id", "user_id")


@dataclass
class CalendarEvent:
    event_id: str
    summary: str
    description: Optional[str]
    start: datetime
    end: datetime
    location: Optional[str]
    attendee_emails: List[str]
    recurrence: List[str]
    reminders: bool
    visibility: str

    def __post_init__(self):
        self.start = convert_to_utc(self.start)
        self.end = convert_to_utc(self.end)


def convert_to_utc(dt: datetime) -> datetime:
    """Convert a datetime object to UTC if it contains time; leave date-only as naive."""
    if dt.tzinfo is None:
        return pytz.utc.localize(dt)
    else:
        return dt.astimezone(pytz.UTC)


TRUST_LABELS = ["CARDINAL", "DATE", "TIME"]


class EntityLabel(enum.Enum):
    GENERAL_GUIDANCE = """
    Do not speculate, base your description strictly on the provided information. 
    The summary should read like a factual report about what the entity is, how it relates to the primary user, 
    and what is known about it. Acknowledge if information about the entity is ambiguous or unclear, rather than 
    inferring information that is not in the provided information.
    
    Keep the content of the summary focused on the entity. This output will be used in conjunction with other similar
    articles about other entities.
    """

    def __new__(cls, *args, **kwds):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, summary_prompt: Optional[str]):
        self.summary_prompt = summary_prompt

    UNKNOWN = None
    PRIMARY_USER = "Synthesize infromation about the personal and professional life of this person. Discuss likes and dislikes, what is important to them, and their relationships with others. As this is the primary user of an AI personal assistant, also discuss their attitudes towards AI personal assistants."
    PERSON = "Synthesize infromation about the personal and professional life of this person. Discuss likes and dislikes, what is important to them, and their relationships with others." + GENERAL_GUIDANCE  # type: ignore
    PET = "Synthesize infromation about about this pet. Discuss things they like, things they dislike, and things about their behavior and care." + GENERAL_GUIDANCE  # type: ignore
    ORG = None
    PRODUCT = None
    WEBSITE = None
    GPE = None
    TVSHOW = None
    BOOK = None
    MOVIE = "Briefly summarize the movie, including the plot, main characters, and any notable aspects." + GENERAL_GUIDANCE  # type: ignore
    TECHNICAL_CONCEPT = None
    MUSICAL_GROUP = (
        "Summarize the musical group, including the members, genre, and notable songs. Discuss how the primary user feels about the group."
    )
    EVENT = "Summarize the event, including the date, location, and a brief description of the event." + GENERAL_GUIDANCE  # type: ignore
    CARDINAL = None
    DATE = "Summarize information about this date, including any signficant events relating to the primary user. Do not include information exclusively about chats between the AI and the user. Instead, focus on the contents of the chats. " + GENERAL_GUIDANCE  # type: ignore
    TIME = None
    AI_ASSISTANT = None
    PROJECT = "Synthesize infromation about the project. This may include the description, who is working on it, what the goal is, and current status." + GENERAL_GUIDANCE  # type: ignore


VALID_LABELS_FOR_CATEGORIZATION = [k for k in EntityLabel.__members__.keys() if k != EntityLabel.PRIMARY_USER.name]
VALID_LABELS_FOR_PERSISTENCE = [k for k in EntityLabel.__members__.keys() if EntityLabel[k].summary_prompt is not None]


@dataclass
class EntityFact:
    name: str
    label: EntityLabel
    text: str

    @classmethod
    def create(cls, name: str, label: str, text: str) -> "EntityFact":
        if label not in EntityLabel.__members__:
            raise ValueError(f"Invalid label {label}")
        else:
            return cls(name=name, label=EntityLabel[label], text=text)

    def __str__(self) -> str:
        return f"EntityFact(name={self.name}, label={self.label}, text={self.text})"


@dataclass
class Entity:
    entity_name: str
    entity_label: EntityLabel
    facts: set[str]
    summary: str


class ArchivalMemory(EmbeddableSqlModel, table=True):
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

    def to_fact(self) -> Fact:
        return Fact(
            name="Archival Memory",
            user_id=self.user_id,
            text="Archival Memory" + "\n" + self.text,
            timestamp=convert_to_utc(self.created_at),
        )


class Goal(EmbeddableSqlModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "name", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="Elroy user whose assistant is being reminded")
    name: str = Field(..., description="The name of the goal")
    description: str = Field(..., description="The description of the goal")
    status_updates: List[str] = Field(
        sa_column=Column(ARRAY(String), nullable=False, server_default="{}"),
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

    def __str__(self) -> str:
        """Return a nicely formatted string representation of the Goal."""
        return (
            f"Goal"
            f"name='{self.name}', "
            f"description='{self.description}', target_completion_time={self.target_completion_time}, "
            f"status_updates={self.status_updates}, strategy='{self.strategy}', "
            f"end_condition='{self.end_condition}', is_active={self.is_active}, "
            f"priority={self.priority})"
        )

    def to_fact(self) -> Fact:
        """Convert the goal to a Fact object."""

        return Fact(
            name=f"Goal: {self.name}",
            user_id=self.user_id,
            timestamp=self.updated_at,
            text=str(self)
            + f"\nInformation about this goal should be kept up to date via AI assistant functions: update_goal_status, and mark_goal_completed",
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
        if self.role != "assistant" and self.tool_calls is not None:
            raise ValueError(f"Only assistant messages can have tool calls, found {self.role} message with tool calls. ID = {self.id}")
        elif self.role != "tool" and self.tool_call_id is not None:
            raise ValueError(f"Only tool messages can have tool call ids, found {self.role} message with tool call id. ID = {self.id}")
        elif self.role == "tool" and self.tool_call_id is None:
            raise ValueError(f"Tool messages must have tool call ids, found tool message without tool call id. ID = {self.id}")
