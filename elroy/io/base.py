import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Iterator, TypeVar, Union

from ..db.db_models import FunctionCall


class ElroyIO(ABC):
    @abstractmethod
    def print(self, message) -> None:
        raise NotImplementedError

    @abstractmethod
    def sys_message(self, message: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def assistant_msg(self, message: Union[str, Iterator[str], Generator[str, None, None]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def notify_function_call(self, function_call: FunctionCall) -> None:
        raise NotImplementedError

    @abstractmethod
    def notify_warning(self, message: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def internal_thought_msg(self, message: str) -> None:
        raise NotImplementedError

    @contextmanager
    def status(self, message: str) -> Generator[None, None, None]:
        logging.info(message)
        yield


IOType = TypeVar("IOType", bound=ElroyIO)


class StdIO(ElroyIO):
    """
    IO which emits plain text to stdin and stdout.
    """

    def print(self, message: Any):
        print(message)

    def sys_message(self, message: str) -> None:
        logging.info(f"[{datetime.now()}] SYSTEM: {message}")

    def assistant_msg(self, message: Union[str, Iterator[str], Generator[str, None, None]]) -> None:
        if isinstance(message, (Iterator, Generator)):
            message = "".join(message)
        print(message)

    def notify_function_call(self, function_call: FunctionCall) -> None:
        logging.info(f"[{datetime.now()}] FUNCTION CALL: {function_call.function_name}({function_call.arguments})")

    def notify_warning(self, message: str) -> None:
        logging.warning(message)

    def internal_thought_msg(self, message: str) -> None:
        logging.info(f"[{datetime.now()}] INTERNAL THOUGHT: {message}")
