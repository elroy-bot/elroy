from dataclasses import dataclass, field
from datetime import datetime
from typing import List, NamedTuple, Optional, Union

from ..db.db_models import ASSISTANT, TOOL, FunctionCall, MemoryMetadata, ToolCall


@dataclass
class ContextMessage:
    content: Optional[str]
    role: str
    chat_model: Optional[str]
    id: Optional[int] = None
    created_at: Optional[datetime] = None
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


class ContentItem(NamedTuple):
    content: str


StreamItem = Union[ContentItem, FunctionCall]
