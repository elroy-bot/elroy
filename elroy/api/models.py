from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from ..utils.clock import string_to_datetime


class MessageResponse(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    messages: List[MessageResponse]


class IngestMemoRequest(BaseModel):
    text: str


class CreateMemoryRequest(BaseModel):
    name: str
    text: str


class ApiResponse(BaseModel):
    result: str


class CreateReminderRequest(BaseModel):
    name: str
    text: str
    trigger_time: Optional[str] = None
    reminder_context: Optional[str] = None

    @property
    def trigger_datetime(self) -> Optional[datetime]:
        if self.trigger_time:
            return string_to_datetime(self.trigger_time)
        else:
            return None


class ReminderResponse(BaseModel):
    id: int
    name: str
    text: str
    trigger_datetime: Optional[str] = None
    reminder_context: Optional[str] = None
