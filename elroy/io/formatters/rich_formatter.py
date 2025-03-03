from typing import Dict, Generator, Union

from rich.console import RenderableType
from rich.pretty import Pretty
from rich.syntax import Syntax
from rich.text import Text

from ...db.db_models import FunctionCall
from ...llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    AssistantToolResult,
    CodeBlock,
    SystemInfo,
    SystemWarning,
    TextOutput,
)
from .base import ElroyPrintable, Formatter


class RichFormatter(Formatter):
    def __init__(
        self,
        system_message_color: str,
        assistant_message_color: str,
        user_input_color: str,
        warning_color: str,
        internal_thought_color: str,
    ) -> None:
        self.system_message_color = system_message_color
        self.assistant_message_color = assistant_message_color
        self.warning_color = warning_color
        self.user_input_color = user_input_color
        self.internal_thought_color = internal_thought_color

    def format(self, message: ElroyPrintable) -> Generator[Union[str, RenderableType], None, None]:
        if isinstance(message, RenderableType):
            yield message
        elif isinstance(message, CodeBlock):
            yield Syntax(
                message.content,
                lexer=message.language or "text",
                theme="monokai",
                line_numbers=False,  # Disabled by default to make copy-paste easier
                word_wrap=True,
                code_width=88,  # Standard Python line length
            )
        elif isinstance(message, FunctionCall):
            text = Text("Executing function call: ", style=self.system_message_color)
            text.append(message.function_name, style=f"bold {self.system_message_color}")
            if message.arguments:
                text.append(f" with arguments: ", style=self.system_message_color)
                yield text
                yield Pretty(message.arguments)
            else:
                yield text
        elif isinstance(message, AssistantToolResult):
            color = self.warning_color if message.is_error else self.system_message_color
            yield Text(message.content, style=color)
        elif isinstance(message, TextOutput):
            styles: Dict[type[TextOutput], str] = {
                AssistantInternalThought: f"italic {self.internal_thought_color}",
                SystemWarning: self.warning_color,
                AssistantResponse: self.assistant_message_color,
                SystemInfo: self.system_message_color,
            }
            yield Text(message.content, style=styles.get(type(message), self.system_message_color))
        elif isinstance(message, Dict):
            yield Pretty(message)
        else:
            raise Exception(f"Unrecognized type: {type(message)}")
