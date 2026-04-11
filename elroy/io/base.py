from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from rich.console import Console, RenderableType

from ..core.logging import get_logger
from ..llm.stream_parser import (
    SystemInfo,
    SystemWarning,
)
from .formatters.base import ElroyPrintable

logger = get_logger()


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

    def info(self, message: str | RenderableType):
        if isinstance(message, str):
            self.print(SystemInfo(content=message))
        else:
            self.print(message)

    def warning(self, message: str | RenderableType):
        if isinstance(message, str):
            self.print(SystemWarning(content=message))
        else:
            self.print(message)

    def prompt_user(self, thread_pool: ThreadPoolExecutor, retries: int, prompt: str = ">", prefill: str = "") -> str:
        raise NotImplementedError
