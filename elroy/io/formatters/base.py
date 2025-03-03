from abc import ABC, abstractmethod
from typing import Dict, Generator, Union

from rich.console import RenderableType

from ...db.db_models import FunctionCall
from ...llm.stream_parser import TextOutput

ElroyPrintable = Union[TextOutput, RenderableType, str, FunctionCall, Dict]


class Formatter(ABC):
    @abstractmethod
    def format(self, message: ElroyPrintable) -> Generator[Union[str, RenderableType], None, None]:
        raise NotImplementedError


class StringFormatter(Formatter):
    @abstractmethod
    def format(self, message: ElroyPrintable) -> Generator[str, None, None]:
        raise NotImplementedError
