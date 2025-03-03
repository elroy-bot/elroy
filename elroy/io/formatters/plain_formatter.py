import json
from typing import Dict, Generator

from ...db.db_models import FunctionCall
from ...llm.stream_parser import AssistantInternalThought, AssistantResponse, TextOutput
from .base import ElroyPrintable, StringFormatter


class PlainFormatter(StringFormatter):

    def format(self, message: ElroyPrintable) -> Generator[str, None, None]:
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
        elif isinstance(message, Dict):
            yield "\n".join(["```json", json.dumps(message, indent=2), "```"])
        else:
            raise Exception(f"Unrecognized type: {type(message)}")
