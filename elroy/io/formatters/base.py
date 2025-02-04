from abc import ABC, abstractmethod
from typing import Generator, Union

from rich.console import RenderableType

from ...db.db_models import FunctionCall
from ...llm.stream_parser import TextOutput


class Formatter(ABC):
    @abstractmethod
    def format(self, message: Union[TextOutput, RenderableType, FunctionCall]) -> Generator[Union[str, RenderableType], None, None]:
        raise NotImplementedError


class StringFormatter(Formatter):
    @abstractmethod
    def format(self, message: Union[TextOutput, RenderableType, FunctionCall]) -> Generator[str, None, None]:
        raise NotImplementedError
