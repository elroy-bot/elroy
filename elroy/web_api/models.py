from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# Goal models
class GoalCreate(BaseModel):
    goal_name: str
    strategy: Optional[str] = None
    description: Optional[str] = None
    end_condition: Optional[str] = None
    time_to_completion: Optional[str] = None
    priority: Optional[int] = None


class GoalStatusUpdate(BaseModel):
    goal_name: str
    status_update_or_note: str


class GoalComplete(BaseModel):
    goal_name: str
    closing_comments: Optional[str] = None


class Goal(BaseModel):
    name: str
    strategy: Optional[str] = None
    description: Optional[str] = None
    end_condition: Optional[str] = None
    time_to_completion: Optional[str] = None
    priority: Optional[int] = None
    status_updates: List[str] = []
    created_at: datetime
    completed_at: Optional[datetime] = None
    is_active: bool = True


# Memory models
class MemoryCreate(BaseModel):
    name: str
    text: str


class MemoryQuery(BaseModel):
    query: str


class Memory(BaseModel):
    name: str
    text: str
    created_at: datetime


# Message models
class MessageRequest(BaseModel):
    input: str
    enable_tools: bool = True


class MessageResponse(BaseModel):
    response: str
    timestamp: datetime


# Document models
class DocIngestRequest(BaseModel):
    address: str
    force_refresh: bool = False


class DocIngestDirRequest(BaseModel):
    address: str
    include: List[str]
    exclude: List[str]
    recursive: bool
    force_refresh: bool = False


class DocIngestResult(BaseModel):
    success: bool
    message: str
    document_name: Optional[str] = None
    document_size: Optional[int] = None
    chunks_created: Optional[int] = None


# Context models
class ContextRefreshResponse(BaseModel):
    refreshed: bool
    timestamp: datetime


# Persona models
class PersonaResponse(BaseModel):
    persona: str
