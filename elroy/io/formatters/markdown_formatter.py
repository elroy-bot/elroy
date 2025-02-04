import json
from typing import Generator, Union

from rich.console import RenderableType

from ...db.db_models import FunctionCall
from ...llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    AssistantToolResult,
    CodeBlock,
    SystemInfo,
    SystemWarning,
    TextOutput,
)
from .base import StringFormatter


class MarkdownFormatter(StringFormatter):
    def format(self, message: Union[TextOutput, RenderableType, FunctionCall]) -> Generator[str, None, None]:

        if isinstance(message, str):
            yield message
        elif isinstance(message, AssistantInternalThought):
            yield f"*{message.content}*"
        elif isinstance(message, AssistantResponse):
            yield message.content
        elif isinstance(message, CodeBlock):
            yield f"```{message.language}\n{message.content}\n```"
        elif isinstance(message, FunctionCall):
            yield f"Executing function call: {message.function_name}"
            if message.arguments:
                yield f"Arguments: {json.dumps(message.arguments, indent=2)}"
        elif isinstance(message, (SystemInfo, SystemWarning)):
            yield f"`{message.content}`"
        elif isinstance(message, AssistantToolResult):
            yield f"```{message.content}```"
        else:
            raise Exception(f"Unrecognized type: {type(message)}")
