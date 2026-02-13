import json
from collections.abc import Generator

from ...db.db_models import FunctionCall
from ...llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    AssistantToolResult,
    CodeBlock,
    SystemInfo,
    SystemWarning,
)
from .base import ElroyPrintable, StringFormatter


class MarkdownFormatter(StringFormatter):
    def format(self, message: ElroyPrintable) -> Generator[str, None, None]:

        if isinstance(message, str):
            yield message
        elif isinstance(message, AssistantInternalThought):
            yield f"*{message.content}*"
        elif isinstance(message, AssistantResponse):
            yield message.content
        elif isinstance(message, CodeBlock):
            yield f"```{message.language}\n{message.content}\n```"
        elif isinstance(message, FunctionCall):
            yield f"```Executing function call: {message.function_name}"
            if message.arguments:
                yield f"Arguments: {json.dumps(message.arguments, indent=2)}"
            yield "```"
        elif isinstance(message, (SystemInfo, SystemWarning)):
            yield f"`{message.content}`"
        elif isinstance(message, AssistantToolResult):
            yield f"```TOOL CALL RESULT: {message.content}```"
        else:
            raise Exception(f"Unrecognized type: {type(message)}")
