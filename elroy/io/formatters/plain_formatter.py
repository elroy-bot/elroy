from typing import Generator, Union

from rich.console import RenderableType

from ...db.db_models import FunctionCall
from ...llm.stream_parser import AssistantInternalThought, AssistantResponse, TextOutput
from .base import StringFormatter


class PlainFormatter(StringFormatter):

    def format(self, message: Union[TextOutput, RenderableType, FunctionCall]) -> Generator[str, None, None]:
        if isinstance(message, str):
            yield message
        elif isinstance(message, AssistantResponse):
            yield message.content
        elif isinstance(message, AssistantInternalThought):
            yield message.content
        elif isinstance(message, TextOutput):
            yield f"{type(message)}: {message}"
        elif isinstance(message, FunctionCall):
            yield f"FUNCTION CALL: {message.function_name}({message.arguments})"
        else:
            raise Exception(f"Unrecognized type: {type(message)}")
