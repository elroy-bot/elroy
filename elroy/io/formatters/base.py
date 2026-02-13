from abc import ABC, abstractmethod
from collections.abc import Generator

from pydantic import BaseModel
from rich.console import RenderableType

ElroyPrintable = BaseModel | RenderableType | str | dict


class Formatter(ABC):
    @abstractmethod
    def format(self, message: ElroyPrintable) -> Generator[str | RenderableType, None, None]:
        raise NotImplementedError


class StringFormatter(Formatter):
    @abstractmethod
    def format(self, message: ElroyPrintable) -> Generator[str, None, None]:
        raise NotImplementedError
