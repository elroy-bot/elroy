"""
Pydantic models for the OpenAI-compatible API server.

This module defines the request and response models for the OpenAI-compatible API,
following the OpenAI API specification.
"""

import time
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Valid message roles in the OpenAI API."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """A message in a conversation."""

    role: MessageRole
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class FunctionCall(BaseModel):
    """A function call in a tool call."""

    name: str
    arguments: str


class ToolCall(BaseModel):
    """A tool call in a message."""

    id: str
    type: Literal["function"] = "function"
    function: FunctionCall


class ChatCompletionRequest(BaseModel):
    """Request model for the chat completions endpoint."""

    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None


class ChatCompletionResponseMessage(BaseModel):
    """A message in a chat completion response."""

    role: MessageRole
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class ChatCompletionResponseChoice(BaseModel):
    """A choice in a chat completion response."""

    index: int
    message: ChatCompletionResponseMessage
    finish_reason: str


class UsageInfo(BaseModel):
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Response model for the chat completions endpoint."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: UsageInfo


class DeltaMessage(BaseModel):
    """A delta message in a streaming response."""

    role: Optional[MessageRole] = None
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class ChatCompletionChunkChoice(BaseModel):
    """A choice in a streaming chat completion response."""

    index: int
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """A chunk in a streaming chat completion response."""

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionChunkChoice]
