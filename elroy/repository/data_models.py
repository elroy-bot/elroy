from datetime import datetime

from pydantic import BaseModel, Field

from ..utils.clock import string_to_datetime


class CreateMemoryRequest(BaseModel):
    name: str = Field(description="Name/title for the memory - should be specific and describe one topic")
    text: str = Field(description="The detailed text content of the memory")


class MemoryResponse(BaseModel):
    name: str = Field(description="The name/title of the memory")
    text: str = Field(description="The text content of the memory")


class CreateReminderRequest(BaseModel):
    name: str = Field(description="Name/title for the reminder")
    text: str = Field(description="The text content of the reminder")
    trigger_time: str | None = Field(
        None, description="When the reminder should trigger (ISO format string). Must be a date in the future, or null"
    )
    reminder_context: str | None = Field(None, description="Additional context for when this reminder should be shown")

    @property
    def trigger_datetime(self) -> datetime | None:
        if self.trigger_time:
            return string_to_datetime(self.trigger_time)
        else:
            return None


class RecallMetadata(BaseModel):
    memory_type: str
    memory_id: int
    name: str


class RecallResponse(BaseModel):
    content: str
    recall_metadata: list[RecallMetadata]  # noqa F841
