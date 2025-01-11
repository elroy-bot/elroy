import logging
from typing import Iterator, Union

from rich.console import Console, RenderableType

from ..db.db_models import FunctionCall
from ..llm.stream_parser import (
    AssistantInternalThought,
    SystemMessage,
    SystemWarning,
    TextOutput,
)


class ElroyIO:
    console: Console

    def print_stream(self, messages: Iterator[Union[TextOutput, RenderableType, FunctionCall]]) -> None:
        for message in messages:
            self.print(message, end="")
        self.console.print("")

    def print(self, message: Union[TextOutput, RenderableType, str, FunctionCall], end: str = "\n") -> None:
        if hasattr(message, "__rich__") or isinstance(message, str):
            self.console.print(message, end)
        else:
            raise NotImplementedError(f"Invalid message type: {type(message)}")

    def internal_thought(self, message: str):
        self.print(AssistantInternalThought(message))

    def info(self, message: Union[str, RenderableType]):
        if isinstance(message, str):
            self.print(SystemMessage(message))
        else:
            self.print(message)

    def warning(self, message: Union[str, RenderableType]):
        if isinstance(message, str):
            self.print(SystemWarning(message))
        else:
            self.print(message)


class StdIO(ElroyIO):
    """
    IO which emits plain text to stdin and stdout.
    """

    def __init__(self):
        self.console = Console(no_color=True)

    def print(self, message: Union[TextOutput, RenderableType, str, FunctionCall], end: str = "\n") -> None:
        if isinstance(message, AssistantInternalThought):
            logging.info(f"{type(message)}: {message}")
        elif isinstance(message, SystemWarning):
            logging.warning(message)
        elif isinstance(message, FunctionCall):
            logging.info(f"FUNCTION CALL: {message.function_name}({message.arguments})")
        elif isinstance(message, TextOutput):
            self.console.print(message.content, end)
        else:
            super().print(message, end)
