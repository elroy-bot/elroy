from collections.abc import Generator

from rich.console import RenderableType
from rich.pretty import Pretty
from rich.syntax import Syntax
from rich.text import Text
from toolz import pipe
from toolz.curried import filter

from ...db.db_models import FunctionCall
from ...llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    AssistantToolResult,
    CodeBlock,
    ShellCommandOutput,
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

    def format(self, message: ElroyPrintable) -> Generator[str | RenderableType, None, None]:
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
                text.append(" with arguments: ", style=self.system_message_color)
                yield text
                yield Pretty(message.arguments)
            else:
                yield text
        elif isinstance(message, AssistantToolResult):
            color = self.warning_color if message.is_error else self.system_message_color
            yield Text(message.content, style=color)
        elif isinstance(message, TextOutput):
            styles: dict[type[TextOutput], str] = {
                AssistantInternalThought: f"italic {self.internal_thought_color}",
                SystemWarning: self.warning_color,
                AssistantResponse: self.assistant_message_color,
                SystemInfo: self.system_message_color,
            }
            yield Text(message.content, style=styles.get(type(message), self.system_message_color))
        elif isinstance(message, ShellCommandOutput):
            # Format the command with syntax highlighting
            yield Syntax(
                message.working_dir + " > " + message.command,
                lexer="bash",  # Use bash lexer for shell commands
                theme="monokai",
                line_numbers=False,
                word_wrap=True,
                code_width=88,
            )

            yield pipe(
                [message.stdout, message.stderr],
                filter(lambda x: x != ""),
                "\n".join,
                lambda x: Syntax(
                    x,
                    lexer="text",
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True,
                    code_width=88,
                ),
            )

        elif isinstance(message, dict):
            yield Pretty(message)
        else:
            raise Exception(f"Unrecognized type: {type(message)}")
