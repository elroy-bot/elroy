from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .utils.clock import string_to_datetime


class MessageResponse(BaseModel):
    role: str = Field(description="The role of the message sender (e.g., 'user' or 'assistant')")
    content: str = Field(description="The content/text of the message")


class ChatRequest(BaseModel):
    message: str = Field(description="The message text to send to the assistant")


class ChatResponse(BaseModel):
    messages: List[MessageResponse] = Field(description="List of messages in the conversation")


class IngestMemoRequest(BaseModel):
    text: str = Field(description="The text content of the memo to ingest")


class IngestMemoResponse(BaseModel):
    reminders: List[str] = Field(description="The names of the reminder that was created")
    memories: List[str] = Field(description="The names of the memory that was created")


class CreateMemoryRequest(BaseModel):
    name: str = Field(description="Name/title for the memory - should be specific and describe one topic")
    text: str = Field(description="The detailed text content of the memory")


class MemoryResponse(BaseModel):
    name: str = Field(description="The name/title of the memory")
    text: str = Field(description="The text content of the memory")


class ApiResponse(BaseModel):
    result: str = Field(description="The result or response from the API operation")


class CreateReminderRequest(BaseModel):
    name: str = Field(description="Name/title for the reminder")
    text: str = Field(description="The text content of the reminder")
    trigger_time: Optional[str] = Field(None, description="When the reminder should trigger (ISO format string)")
    reminder_context: Optional[str] = Field(None, description="Additional context for when this reminder should be shown")

    @property
    def trigger_datetime(self) -> Optional[datetime]:
        if self.trigger_time:
            return string_to_datetime(self.trigger_time)
        else:
            return None


class CompleteReminderRequest(BaseModel):
    name: str = Field(description="Name of the reminder to mark complete")
    closing_comment: Optional[str] = Field(None, description="Optional comment on why the reminder was completed")


class ReminderResponse(BaseModel):
    id: int = Field(description="Unique identifier for the reminder")
    name: str = Field(description="Name/title of the reminder")
    text: str = Field(description="The text content of the reminder")
    trigger_datetime: Optional[str] = Field(None, description="When the reminder triggers (ISO format string)")
    reminder_context: Optional[str] = Field(None, description="Additional context for the reminder")


class RecallMetadata(BaseModel):
    memory_type: str
    memory_id: int
    name: str


class RecallResponse(BaseModel):
    content: str
    recall_metadata: List[RecallMetadata]  # noqa F841
