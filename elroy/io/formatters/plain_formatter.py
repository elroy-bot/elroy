import json
from collections.abc import Generator

from ...db.db_models import FunctionCall
from ...llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    ShellCommandOutput,
    TextOutput,
)
from .base import ElroyPrintable, StringFormatter


class PlainFormatter(StringFormatter):
    def format(self, message: ElroyPrintable) -> Generator[str, None, None]:
        if isinstance(message, (str, AssistantResponse, AssistantInternalThought)):
            yield str(message)
        elif isinstance(message, TextOutput):
            yield f"{type(message)}: {message}"
        elif isinstance(message, FunctionCall):
            yield f"FUNCTION CALL: {message.function_name}({message.arguments})"
        elif isinstance(message, ShellCommandOutput):
            output = [f"{message.working_dir} > {message.command}"]
            if message.stdout:
                output.append("Standard Output:")
                output.append(message.stdout)
            if message.stderr:
                output.append("Standard Error:")
                output.append(message.stderr)
            yield "\n".join(output)
        elif isinstance(message, dict):
            yield "\n".join(["```json", json.dumps(message, indent=2), "```"])
        else:
            raise Exception(f"Unrecognized type: {type(message)}")
