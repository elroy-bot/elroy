from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generator, Iterator, Union

from elroy.store.data_models import FunctionCall


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

class StdIO(ElroyIO):
    """
    IO which emits plain text to stdin and stdout.
    """

    def sys_message(self, message: str) -> None:
        print(f"[{datetime.now()}] SYSTEM: {message}")

    def assistant_msg(self, message: Union[str, Iterator[str], Generator[str, None, None]]) -> None:
        if isinstance(message, (Iterator, Generator)):
            message = "".join(message)
        print(f"[{datetime.now()}] ASSISTANT: {message}")

    def notify_function_call(self, function_call: FunctionCall) -> None:
        print(f"[{datetime.now()}] FUNCTION CALL: {function_call.function_name}({function_call.arguments})")

    def notify_function_call_error(self, function_call: FunctionCall, error: Exception) -> None:
        print(f"[{datetime.now()}] FUNCTION ERROR: {function_call.function_name} - {str(error)}")

    def notify_warning(self, message: str) -> None:
        print(f"[{datetime.now()}] WARNING: {message}")

class TestIO(ElroyIO):
    """
    IO which simply logs calls to its methods, with output.
    """

    def __init__(self):
        self.system_messages: list[str] = []
        self.assistant_messages: list[str] = []
        self.function_calls: list[FunctionCall] = []
        self.function_call_errors: list[tuple[FunctionCall, Exception]] = []
        self.warnings: list[str] = []

    def sys_message(self, message: str) -> None:
        print(f"[{datetime.now()}] SYSTEM: {message}")
        self.system_messages.append(message)

    def assistant_msg(self, message: Union[str, Iterator[str], Generator[str, None, None]]) -> None:
        if isinstance(message, (Iterator, Generator)):
            message = "".join(message)
        print(f"[{datetime.now()}] ASSISTANT: {message}")
        self.assistant_messages.append(message)

    def notify_function_call(self, function_call: FunctionCall) -> None:
        print(f"[{datetime.now()}] FUNCTION CALL: {function_call.function_name}({function_call.arguments})")
        self.function_calls.append(function_call)

    def notify_function_call_error(self, function_call: FunctionCall, error: Exception) -> None:
        print(f"[{datetime.now()}] FUNCTION ERROR: {function_call.function_name} - {str(error)}")
        self.function_call_errors.append((function_call, error))

    def notify_warning(self, message: str) -> None:
        print(f"[{datetime.now()}] WARNING: {message}")
        self.warnings.append(message)
