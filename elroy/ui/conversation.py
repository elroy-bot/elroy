"""Conversation/history controller for the Textual app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from ..db.db_models import FunctionCall
from ..llm.stream_parser import AssistantInternalThought, AssistantResponse, AssistantToolResult, StreamTextProcessor, collect

if TYPE_CHECKING:
    from .commands import ToolCommandSpec


class ConversationController:
    """Coordinates chat history rendering, streaming buffers, and prompt history."""

    def __init__(self, formatter, prompt_history, show_internal_thought: bool):
        self.formatter = formatter
        self.prompt_history = prompt_history
        self.show_internal_thought = show_internal_thought
        self._streaming_buffer = ""
        self._streaming_style = ""
        self._thought_buffer = ""
        self._input_history = self.prompt_history.load()

    @property
    def input_history(self) -> list[str]:
        return self._input_history

    def remember_prompt(self, text: str) -> None:
        self.prompt_history.append(text)
        self._input_history.insert(0, text)

    def write_to_history(self, conversation_pane, renderable) -> None:
        conversation_pane.write_history(renderable)

    def append_streaming_token(self, conversation_pane, token: str, style: str) -> None:
        self._streaming_buffer += token
        self._streaming_style = style
        conversation_pane.set_streaming_text(self._streaming_buffer, style)

    def flush_streaming_buffer(self, conversation_pane) -> None:
        if self._streaming_buffer:
            self.write_to_history(conversation_pane, Text(self._streaming_buffer, style=self._streaming_style))
            self._streaming_buffer = ""
            self._streaming_style = ""
        conversation_pane.clear_streaming()

    def append_thought_token(self, token: str) -> None:
        self._thought_buffer += token

    def flush_thought_buffer(self, conversation_pane) -> None:
        if self._thought_buffer:
            style = f"italic {self.formatter.internal_thought_color}"
            self.write_to_history(conversation_pane, Text(self._thought_buffer, style=style))
            self._thought_buffer = ""

    def _render_assistant_content(self, conversation_pane, content: str) -> None:
        processor = StreamTextProcessor()
        chunks = collect(iter([*processor.process(content), *processor.flush()]))
        for chunk in chunks:
            if isinstance(chunk, AssistantInternalThought):
                if not self.show_internal_thought:
                    continue
                self.write_to_history(
                    conversation_pane,
                    Text(chunk.content, style=f"italic {self.formatter.internal_thought_color}"),
                )
            elif isinstance(chunk, AssistantResponse):
                self.write_to_history(conversation_pane, Text(chunk.content, style=self.formatter.assistant_message_color))
            elif isinstance(chunk, FunctionCall):
                renderable = next(self.formatter.format(chunk))
                self.write_to_history(conversation_pane, renderable)

    @staticmethod
    def _is_bootstrap_tool_call_message(message, bootstrap_tool_call_ids: set[str]) -> bool:
        return bool(
            message.role == "assistant"
            and message.tool_calls
            and any(tool_call.id in bootstrap_tool_call_ids for tool_call in message.tool_calls)
        )

    def render_existing_context_messages(self, conversation_pane, context_messages: list, bootstrap_tool_call_ids: set[str]) -> None:
        for index, message in enumerate(context_messages):
            if message.role == "system":
                continue
            next_message = context_messages[index + 1] if index + 1 < len(context_messages) else None
            if (
                message.role == "user"
                and next_message is not None
                and self._is_bootstrap_tool_call_message(next_message, bootstrap_tool_call_ids)
            ):
                continue
            if self._is_bootstrap_tool_call_message(message, bootstrap_tool_call_ids):
                continue
            if message.role == "tool" and message.tool_call_id in bootstrap_tool_call_ids:
                continue
            if not message.content:
                continue

            if message.role == "user":
                renderable = Text(f"\nYou: {message.content}", style=self.formatter.user_input_color)
            elif message.role == "assistant":
                self._render_assistant_content(conversation_pane, message.content)
                continue
            elif message.role == "tool":
                renderable = next(self.formatter.format(AssistantToolResult(content=message.content, is_error=False)))
            else:
                renderable = Text(message.content, style=self.formatter.system_message_color)

            self.write_to_history(conversation_pane, renderable)

    def display_command_result(self, conversation_pane, notify, result, spec: ToolCommandSpec, source: str) -> None:
        if isinstance(result, str):
            if source == "palette" and spec.result_target == "toast" and "\n" not in result and len(result) <= 180:
                notify(result)
            else:
                self.write_to_history(conversation_pane, Text(result, style=self.formatter.system_message_color))
        else:
            self.write_to_history(conversation_pane, result)

    def accept_input_completion(self, input_widget, suggestions: list[str]) -> None:
        if input_widget.cursor_location[1] != len(input_widget.value):
            return

        prefix = input_widget.value
        if not prefix:
            return

        match = next(
            (suggestion for suggestion in suggestions if suggestion.lower().startswith(prefix.lower()) and suggestion != prefix), None
        )
        if match:
            input_widget.value = match
