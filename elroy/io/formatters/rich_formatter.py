import json
from collections.abc import Generator

from pydantic import BaseModel
from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
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
from ...repository.data_models import AgendaListResponse
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

    def _format_json_block(self, data: dict | list) -> Syntax:
        return Syntax(
            json.dumps(data, indent=2),
            lexer="json",
            theme="monokai",
            line_numbers=False,
            word_wrap=True,
            code_width=88,
        )

    def _tool_panel(self, title: str, body: RenderableType, color: str) -> Panel:
        return Panel(
            body,
            title=title,
            title_align="left",
            border_style=color,
            padding=(0, 1),
            expand=True,
        )

    def _format_key_value_rows(self, data: dict[str, object]) -> Table:
        table = Table(
            box=box.SIMPLE,
            show_header=False,
            expand=True,
            pad_edge=False,
        )
        table.add_column("Key", style=f"bold {self.system_message_color}", no_wrap=True, ratio=1)
        table.add_column("Value", style=self.system_message_color, ratio=4)
        for key, value in data.items():
            table.add_row(key, "" if value is None else str(value))
        return table

    def _format_agenda_list(self, message: AgendaListResponse) -> RenderableType:
        if not message.items:
            return Text(f"No agenda items for {message.item_date}.", style=self.system_message_color)

        table = Table(box=box.SIMPLE, expand=True, pad_edge=False)
        table.add_column("Item", style=f"bold {self.system_message_color}", no_wrap=True, ratio=2)
        table.add_column("Text", style=self.system_message_color, ratio=5)
        table.add_column("Checklist", style=self.system_message_color, no_wrap=True, ratio=1)
        for item in message.items:
            table.add_row(item.name, item.text, item.checklist_progress)
        return table

    def _format_structured_model(self, message: BaseModel) -> RenderableType:
        if isinstance(message, AgendaListResponse):
            return self._tool_panel(
                f"Agenda for {message.item_date}",
                self._format_agenda_list(message),
                self.system_message_color,
            )
        return self._tool_panel("Tool Result", self._format_json_block(message.model_dump(mode="json")), self.system_message_color)

    def _format_code_block(self, message: CodeBlock) -> Syntax:
        return Syntax(
            message.content,
            lexer=message.language or "text",
            theme="monokai",
            line_numbers=False,
            word_wrap=True,
            code_width=88,
        )

    def _format_function_call(self, message: FunctionCall) -> Panel:
        body: list[RenderableType] = [Text(message.function_name, style=f"bold {self.system_message_color}")]
        if message.arguments:
            if all(not isinstance(v, dict | list) for v in message.arguments.values()):
                body.append(self._format_key_value_rows(message.arguments))
            else:
                body.append(self._format_json_block(message.arguments))
        return self._tool_panel("Tool Call", Group(*body), self.system_message_color)

    def _format_text_output(self, message: TextOutput) -> Text:
        styles: dict[type[TextOutput], str] = {
            AssistantInternalThought: f"italic {self.internal_thought_color}",
            SystemWarning: self.warning_color,
            AssistantResponse: self.assistant_message_color,
            SystemInfo: self.system_message_color,
        }
        return Text(message.content, style=styles.get(type(message), self.system_message_color))

    def _format_shell_command_output(self, message: ShellCommandOutput) -> Generator[RenderableType, None, None]:
        yield Syntax(
            message.working_dir + " > " + message.command,
            lexer="bash",
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

    def _tool_result_body(self, content: str) -> RenderableType:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return Text(content, style=self.system_message_color)

        if isinstance(parsed, dict) and {"item_date", "items"} <= parsed.keys():
            try:
                return self._format_agenda_list(AgendaListResponse.model_validate(parsed))
            except Exception:
                pass
        if isinstance(parsed, dict) and parsed and all(not isinstance(v, dict | list) for v in parsed.values()):
            return self._format_key_value_rows(parsed)
        if isinstance(parsed, dict | list):
            return self._format_json_block(parsed)
        return Text(content, style=self.system_message_color)

    def format(self, message: ElroyPrintable) -> Generator[str | RenderableType, None, None]:
        if isinstance(message, RenderableType):
            yield message
        elif isinstance(message, CodeBlock):
            yield self._format_code_block(message)
        elif isinstance(message, FunctionCall):
            yield self._format_function_call(message)
        elif isinstance(message, AssistantToolResult):
            color = self.warning_color if message.is_error else self.system_message_color
            title = "Tool Error" if message.is_error else "Tool Result"
            yield self._tool_panel(title, self._tool_result_body(message.content), color)
        elif isinstance(message, BaseModel):
            yield self._format_structured_model(message)
        elif isinstance(message, TextOutput):
            yield self._format_text_output(message)
        elif isinstance(message, ShellCommandOutput):
            yield from self._format_shell_command_output(message)
        elif isinstance(message, dict):
            yield Text(json.dumps(message, indent=2), style=self.system_message_color)
        else:
            raise TypeError(f"Unrecognized type: {type(message)}")
