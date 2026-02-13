from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from ...core.constants import ASSISTANT, TOOL
from ...db.db_models import ToolCall
from ...utils.clock import utc_now


@dataclass
class ContextMessage:
    content: str | None
    role: str
    chat_model: str | None
    id: int | None = None
    created_at: datetime = field(default_factory=utc_now)
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

    def as_dict(self):
        return {
            "content": self.content,
            "role": self.role,
            "chat_model": self.chat_model,
            "id": self.id,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at is not None else None,
            "tool_calls": [tc.to_json() for tc in self.tool_calls] if self.tool_calls is not None else None,
            "tool_call_id": self.tool_call_id,
        }

    def __post_init__(self):
        if self.tool_calls is not None:
            self.tool_calls = [ToolCall(**cast(dict[str, Any], tc)) if isinstance(tc, dict) else tc for tc in self.tool_calls]
        # as per openai requirements, empty arrays are disallowed
        if self.tool_calls == []:
            self.tool_calls = None
        if self.role != ASSISTANT and self.tool_calls is not None:
            raise ValueError(f"Only assistant messages can have tool calls, found {self.role} message with tool calls. ID = {self.id}")
        elif self.role != TOOL and self.tool_call_id is not None:
            raise ValueError(f"Only tool messages can have tool call ids, found {self.role} message with tool call id. ID = {self.id}")
        elif self.role == TOOL and self.tool_call_id is None:
            raise ValueError(f"Tool messages must have tool call ids, found tool message without tool call id. ID = {self.id}")
