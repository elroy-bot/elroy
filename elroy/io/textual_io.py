"""TextualIO: bridges Elroy's streaming output to the Textual TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console

from ..io.base import ElroyIO
from ..io.formatters.rich_formatter import RichFormatter

if TYPE_CHECKING:
    from ..io.textual_app import ElroyApp


class TextualIO(ElroyIO):
    """IO implementation that writes to the Textual app."""

    def __init__(self, app: ElroyApp, formatter: RichFormatter, show_internal_thought: bool) -> None:
        self.app = app
        self.formatter = formatter
        self.show_internal_thought = show_internal_thought
        self.console = Console()  # kept for ElroyIO compatibility

    def print(self, message, end: str = "\n") -> None:
        from ..core.logging import get_logger
        from ..llm.stream_parser import AssistantInternalThought, AssistantResponse, AssistantToolResult, StatusUpdate

        logger = get_logger()

        if isinstance(message, StatusUpdate):
            return  # handled by _run_stream directly; never written to chat history

        if isinstance(message, AssistantInternalThought):
            if not self.show_internal_thought:
                logger.debug(f"Internal thought: {message}")
                return
            self.app.call_from_thread(self.app._append_thought_token, message.content)
            return

        self.app.call_from_thread(self.app._flush_thought_buffer)

        if isinstance(message, AssistantToolResult) and len(message.content) > 500:
            message = AssistantToolResult(
                content=f"< {len(message.content)} char tool result >",
                is_error=message.is_error,
            )

        if isinstance(message, AssistantResponse):
            self.app.call_from_thread(
                self.app._append_streaming_token,
                message.content,
                self.formatter.assistant_message_color,
            )
        else:
            for renderable in self.formatter.format(message):
                self.app.call_from_thread(self.app._write_to_history, renderable)

    def info(self, message) -> None:
        from ..llm.stream_parser import SystemInfo

        if isinstance(message, str):
            self.print(SystemInfo(content=message))
        else:
            self.print(message)

    def warning(self, message) -> None:
        from ..llm.stream_parser import SystemWarning

        if isinstance(message, str):
            self.print(SystemWarning(content=message))
        else:
            self.print(message)
