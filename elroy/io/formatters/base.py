from abc import ABC, abstractmethod
from typing import Dict, Generator, Union

from pydantic import BaseModel
from rich.console import RenderableType

ElroyPrintable = Union[BaseModel, RenderableType, str, Dict]


class Formatter(ABC):
    @abstractmethod
    def format(self, message: ElroyPrintable) -> Generator[Union[str, RenderableType], None, None]:
        raise NotImplementedError


class StringFormatter(Formatter):
    @abstractmethod
    def format(self, message: ElroyPrintable) -> Generator[str, None, None]:
        raise NotImplementedError
