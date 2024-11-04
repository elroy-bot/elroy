import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, Iterator, Union

from ..repository.data_models import FunctionCall


class ElroyIO(ABC):

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
    def notify_function_call_error(self, function_call: FunctionCall, error: Exception) -> None:
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


class StdIO(ElroyIO):
    """
    IO which emits plain text to stdin and stdout.
    """

    def sys_message(self, message: str) -> None:
        logging.info(f"[{datetime.now()}] SYSTEM: {message}")

    def assistant_msg(self, message: Union[str, Iterator[str], Generator[str, None, None]]) -> None:
        if isinstance(message, (Iterator, Generator)):
            message = "".join(message)
        print(message)

    def notify_function_call(self, function_call: FunctionCall) -> None:
        logging.info(f"[{datetime.now()}] FUNCTION CALL: {function_call.function_name}({function_call.arguments})")

    def notify_function_call_error(self, function_call: FunctionCall, error: Exception) -> None:
        logging.error(f"[{datetime.now()}] FUNCTION ERROR: {function_call.function_name} - {str(error)}")

    def notify_warning(self, message: str) -> None:
        logging.warning(message)

    def internal_thought_msg(self, message: str) -> None:
        logging.info(f"[{datetime.now()}] INTERNAL THOUGHT: {message}")
