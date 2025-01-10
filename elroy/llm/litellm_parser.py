import json
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional

from litellm.types.utils import ModelResponse

from ..config.config import ChatModel
from ..db.db_models import FunctionCall
from ..repository.data_models import AssistantResponseChunk, StreamItem
from .parser import StreamParser


class LiteLlmParser(StreamParser):
    def __init__(self, chat_model: ChatModel):
        self.tool_call_accumulator = ToolCallAccumulator(chat_model)

    def process(self, chunks: Iterator[ModelResponse]) -> Iterator[StreamItem]:
        for chunk in chunks:
            if chunk.choices[0].delta.content:  # type: ignore
                yield AssistantResponseChunk(content=chunk.choices[0].delta.content)  # type: ignore
            if chunk.choices[0].delta.tool_calls:  # type: ignore
                yield from tool_call_accumulator.update(chunk.choices[0].delta.tool_calls)  # type: ignore


@dataclass
class PartialToolCall:
    id: str
    model: str  # Add model parameter to determine format
    function_name: str = ""
    arguments: str = ""
    type: str = "function"
    is_complete: bool = False

    from litellm.types.utils import ChatCompletionDeltaToolCall

    def update(self, delta: ChatCompletionDeltaToolCall) -> Optional[FunctionCall]:
        from litellm.types.utils import ChatCompletionDeltaToolCall

        if self.is_complete:
            raise ValueError("PartialToolCall is already complete")

        assert isinstance(delta, ChatCompletionDeltaToolCall), f"Expected ChoiceDeltaToolCall, got {type(delta)}"
        assert delta.function
        if delta.function.name:
            self.function_name += delta.function.name
        if delta.function.arguments:
            self.arguments += delta.function.arguments

        # Check if we have a complete JSON object for arguments
        try:
            function_call = FunctionCall(
                id=self.id,
                function_name=self.function_name,
                arguments=json.loads(self.arguments),
            )
            self.is_complete = True
            return function_call
        except json.JSONDecodeError:
            return None


class ToolCallAccumulator:
    from litellm.types.utils import ChatCompletionDeltaToolCall

    def __init__(self, chat_model: ChatModel):
        self.chat_model = chat_model
        self.tool_calls: Dict[int, PartialToolCall] = {}
        self.last_updated_index: Optional[int] = None

    def update(self, delta_tool_calls: Optional[List[ChatCompletionDeltaToolCall]]) -> Iterator[FunctionCall]:
        for delta in delta_tool_calls or []:
            if delta.index not in self.tool_calls:
                if (
                    self.last_updated_index is not None
                    and self.last_updated_index in self.tool_calls
                    and self.last_updated_index != delta.index
                ):
                    raise ValueError("New tool call started, but old one is not yet complete")
                assert delta.id
                self.tool_calls[delta.index] = PartialToolCall(id=delta.id, model=self.chat_model.name)

            completed_tool_call = self.tool_calls[delta.index].update(delta)
            if completed_tool_call:
                self.tool_calls.pop(delta.index)
                yield completed_tool_call
            else:
                self.last_updated_index = delta.index
