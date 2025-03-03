import logging
from typing import Any, Iterator, Union

from rich.console import Console, RenderableType

from ..db.db_models import FunctionCall
from ..llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    SystemInfo,
    SystemWarning,
)
from .formatters.base import ElroyPrintable
from .formatters.plain_formatter import PlainFormatter


def is_rich_printable(obj: Any) -> bool:
    return isinstance(obj, str) or hasattr(obj, "__rich__") or hasattr(obj, "__rich_console__")


class ElroyIO:
    console: Console

    def print_stream(self, messages: Iterator[ElroyPrintable]) -> None:
        for message in messages:
            self.print(message, end="")
        self.console.print("")

    def print(self, message: ElroyPrintable, end: str = "\n") -> None:
        if is_rich_printable(message):
            self.console.print(message, end)
        else:
            raise NotImplementedError(f"Invalid message type: {type(message)}")

    def info(self, message: Union[str, RenderableType]):
        if isinstance(message, str):
            self.print(SystemInfo(message))
        else:
            self.print(message)

    def warning(self, message: Union[str, RenderableType]):
        if isinstance(message, str):
            self.print(SystemWarning(message))
        else:
            self.print(message)


class PlainIO(ElroyIO):
    """
    IO which emits plain text to stdin and stdout.
    """

    def __init__(self) -> None:
        self.console = Console(force_terminal=False, no_color=True)
        self.formatter = PlainFormatter()

    def print(self, message: ElroyPrintable, end: str = "\n") -> None:
        if is_rich_printable(message):
            self.console.print(message, end)
        elif isinstance(message, AssistantResponse):
            for output in self.formatter.format(message):
                self.console.print(output, end=end)
        elif isinstance(message, AssistantInternalThought):
            logging.info(f"{type(message)}: {message}")
        elif isinstance(message, SystemWarning):
            logging.warning(message)
        elif isinstance(message, FunctionCall):
            logging.info(f"FUNCTION CALL: {message.function_name}({message.arguments})")
        elif isinstance(message, SystemInfo):
            logging.info(message)
        else:
            raise NotImplementedError(f"Invalid message type: {type(message)}")
