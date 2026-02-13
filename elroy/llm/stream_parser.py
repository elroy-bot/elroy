import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from typing import Generic, TypeVar

from litellm.types.utils import Delta, ModelResponse
from pydantic import BaseModel

from ..config.llm import ChatModel
from ..core.logging import get_logger
from ..db.db_models import FunctionCall
from .tool_call_accumulator import OpenAIToolCallAccumulator

logger = get_logger()


class TextOutput(BaseModel):
    content: str

    def __str__(self):
        return self.content


class AssistantInternalThought(TextOutput):
    content: str


class AssistantResponse(TextOutput):
    content: str


class AssistantToolResult(TextOutput):
    content: str
    is_error: bool = False


class SystemInfo(TextOutput):
    content: str


class SystemWarning(TextOutput):
    content: str


class CodeBlock(BaseModel):
    """Represents a code block that can be formatted with Rich"""

    content: str
    language: str = ""  # Optional language for syntax highlighting

    def __str__(self) -> str:
        return f"```{self.language}\n{self.content}```"


class ShellCommandOutput(BaseModel):
    """Model representing a shell command execution with its context and result"""

    working_dir: str
    command: str
    stdout: str
    stderr: str

    def __str__(self) -> str:
        return f"""{self.working_dir} > {self.command}\nself.stdout\n{self.stdout}\nself.stderr\n{self.stderr}"""


def to_openai_tool_call(content: str) -> FunctionCall | None:
    try:
        d = json.loads(content)
        if d.get("name") and d.get("arguments"):
            return FunctionCall(id=uuid.uuid4().hex, function_name=d["name"], arguments=d["arguments"])
    except Exception:
        pass


@dataclass
class TagSet:
    begin_tag: str
    end_tag: str


T = TypeVar("T", bound=BaseModel)


class TextProcessor(ABC, Generic[T]):
    tags: list[TagSet]

    def __init__(self):
        self.buffer = ""
        self.active_tag = None

    def is_active(self) -> bool:
        return self.active_tag is not None

    def activate(self, begin_tag: str):
        self.active_tag = next(tag for tag in self.tags if tag.begin_tag == begin_tag)

    def deactivate(self) -> None:
        assert len(self.buffer) == 0
        self.active_tag = None

    def process(self, text: str) -> Generator[T, None, None]:
        assert self.active_tag
        assert len(text) == 1
        self.buffer += text

        if not text.isspace():
            while self.buffer:
                if self.buffer.lstrip().endswith(self.active_tag.end_tag):
                    self.buffer = self.buffer[: -len(self.buffer)].lstrip()
                    yield from self.flush()
                    self.deactivate()
                    return
                elif self.active_tag.end_tag.startswith(self.buffer.lstrip()):
                    break
                else:
                    yield from self.maybe_consume_buffer()
                    break

    @abstractmethod
    def maybe_consume_buffer(self) -> Generator[T, None, None]:
        """
        Consumes buffer if possible and returns output.
        Responsible for resetting buffer to empty string if buffer can be consumed
        """
        raise NotImplementedError

    @abstractmethod
    def flush(self) -> Generator[T, None, None]:
        raise NotImplementedError


class InternalThoughtProcessor(TextProcessor[AssistantInternalThought]):
    tags: list[TagSet] = [TagSet("<internal_thought>", "</internal_thought>"), TagSet("<think>", "</think>")]
    first_non_whitespace_emitted: bool = False

    def activate(self, begin_tag: str):
        super().activate(begin_tag)
        self.first_non_whitespace_emitted = False

    def maybe_consume_buffer(self) -> Generator[AssistantInternalThought, None, None]:
        if self.first_non_whitespace_emitted:
            yield AssistantInternalThought(content=self.buffer)
            self.buffer = ""
        elif not self.buffer.isspace():
            self.first_non_whitespace_emitted = True
            resp = AssistantInternalThought(content=self.buffer.lstrip())
            self.buffer = ""
            yield resp

        else:
            # Ignore leading whitespace
            pass

    def flush(self) -> Generator[AssistantInternalThought, None, None]:
        if self.buffer:
            yield AssistantInternalThought(content=self.buffer)
        self.deactivate()


class CodeBlockProcessor(TextProcessor[CodeBlock]):
    """Processes Markdown-style code blocks with backticks"""

    tags = [TagSet("```", "```")]  # Using backticks as tag

    def __init__(self):
        super().__init__()
        self.language = ""
        self.in_header = True  # True until we see first newline
        self.content_lines = []

    def activate(self, begin_tag: str):
        super().activate(begin_tag)
        self.language = ""
        self.in_header = True
        self.content_lines = []

    def maybe_consume_buffer(self) -> Generator[CodeBlock, None, None]:
        if self.in_header and "\n" in self.buffer:
            # Extract language from header line
            header, rest = self.buffer.split("\n", 1)
            self.language = header.strip()
            self.buffer = rest
            self.in_header = False

        if not self.in_header and "\n" in self.buffer:
            lines = self.buffer.split("\n")
            self.buffer = lines[-1]  # Keep last incomplete line

            for line in lines[:-1]:
                if line.rstrip() == "```":  # End of code block
                    if self.content_lines:  # Emit accumulated lines
                        yield CodeBlock(content="\n".join(self.content_lines) + "\n", language=self.language)
                    self.deactivate()
                    return
                self.content_lines.append(line)

    def flush(self) -> Generator[CodeBlock, None, None]:
        if self.content_lines:
            # Remove trailing backticks if present
            content = self.content_lines[:]
            if self.buffer.rstrip() == "```":
                self.buffer = ""
            elif self.buffer:
                content.append(self.buffer)

            yield CodeBlock(content="\n".join(content) + "\n", language=self.language)
        self.buffer = ""
        self.content_lines = []
        self.deactivate()


class InlineToolCallProcessor(TextProcessor[FunctionCall]):
    tags = [TagSet("<tool_call>", "</tool_call>")]

    def maybe_consume_buffer(self) -> Generator[FunctionCall, None, None]:
        tool_call = to_openai_tool_call(self.buffer)
        if tool_call:
            self.buffer = ""
            yield tool_call

    def flush(self) -> Generator[FunctionCall, None, None]:
        if self.buffer:
            tool_call = to_openai_tool_call(self.buffer)
            if tool_call:
                self.buffer = ""
                self.deactivate()
                yield tool_call
            else:
                logger.warning("Buffer not empty, but cannot be converted to tool call")
                self.deactivate()
                self.buffer = ""


class AssistantResponseProcessor:
    """Processes regular text output with proper whitespace handling"""

    tags: list[TagSet] = []  # No tags since this handles regular text
    first_non_whitespace_emitted: bool = False

    def __init__(self):
        super().__init__()
        self.buffer = ""
        self.first_non_whitespace_emitted = False

    def activate(self):
        self.first_non_whitespace_emitted = False

    def deactivate(self):
        self.first_non_whitespace_emitted = False

    def process(self, text: str) -> Generator[AssistantResponse, None, None]:
        self.buffer += text
        if self.first_non_whitespace_emitted:
            if not self.buffer.isspace():
                yield AssistantResponse(content=self.buffer)
                self.buffer = ""
        elif not self.buffer.isspace():
            self.first_non_whitespace_emitted = True
            resp = AssistantResponse(content=self.buffer.lstrip())
            self.buffer = ""
            yield resp
        else:
            # Ignore leading whitespace
            pass

    def flush(self) -> Generator[AssistantResponse, None, None]:
        if self.buffer and not self.buffer.isspace():
            yield AssistantResponse(content=self.buffer.rstrip())
        self.buffer = ""
        self.deactivate()


class StreamTextProcessor:
    def __init__(self):
        self.processors: list[TextProcessor] = [
            CodeBlockProcessor(),  # Process code blocks first
            InlineToolCallProcessor(),
            InternalThoughtProcessor(),
        ]
        self.buffer = ""
        self.active_processor: TextProcessor | None = None
        self.default_processor = AssistantResponseProcessor()
        self.default_processor.activate()  # Activate with empty tag since it handles regular text

    def process(self, text: str) -> Generator[TextOutput | FunctionCall, None, None]:
        for char in text:
            self.buffer += char
            yield from self.process_buffer()

    def process_buffer(self) -> Generator[TextOutput | FunctionCall, None, None]:
        while len(self.buffer) > 0:
            if self.active_processor:
                assert self.buffer
                yield from self.active_processor.process(self.buffer[0])
                self.buffer = self.buffer[1:]
                if not self.active_processor.is_active():
                    self.active_processor = None
            else:
                partial_tag_match_found = False
                for processor in self.processors:
                    assert not processor.is_active(), "unexpected active stream processor"

                    for tag in processor.tags:
                        if tag.begin_tag == self.buffer:
                            self.active_processor = processor
                            self.active_processor.activate(tag.begin_tag)
                            self.buffer = ""
                            yield from self.default_processor.flush()
                            break
                        elif tag.begin_tag.startswith(self.buffer):
                            partial_tag_match_found = True
                if partial_tag_match_found:
                    # We should not consume the buffer, we may have started a tag but not finished it"""
                    return
                else:
                    if len(self.buffer) > 0:
                        assert self.buffer
                        yield from self.default_processor.process(self.buffer[0])
                        self.buffer = self.buffer[1:]

    def flush(self) -> Generator[TextOutput | FunctionCall, None, None]:
        if self.buffer:
            if self.active_processor:
                yield from self.active_processor.flush()
            else:
                yield from self.default_processor.flush()
            self.buffer = ""


class StreamParser:
    """
    Wraps text processors, to handle:
    - stripping trailing whitespace
    - handling tool calls
    - flushing

    """

    def __init__(self, chat_model: ChatModel, chunks: Iterator[ModelResponse]):
        self.chunks = chunks
        self.openai_tool_call_accumulator = OpenAIToolCallAccumulator(chat_model)
        self.stream_text_processor = StreamTextProcessor()
        self.raw_text = ""

    def process_stream(self) -> Generator[TextOutput | FunctionCall, None, None]:
        for chunk in self.chunks:
            delta = chunk.choices[0].delta  # type: ignore
            assert isinstance(delta, Delta)
            if delta.tool_calls:
                yield from self.openai_tool_call_accumulator.update(delta.tool_calls)
            if delta.content:
                text = delta.content
                if not self.raw_text:
                    self.raw_text = text
                else:
                    self.raw_text += text
                assert isinstance(text, str)
                yield from self.stream_text_processor.process(text)
        yield from self.stream_text_processor.flush()

    def get_full_text(self) -> str:
        return self.raw_text


def collect(input_stream: Iterator[BaseModel]) -> list[BaseModel]:
    response = []
    for processed_chunk in input_stream:
        if isinstance(processed_chunk, TextOutput):
            if len(response) == 0 or type(response[-1]) is not type(processed_chunk):
                response.append(processed_chunk)
            else:
                response[-1].content += processed_chunk.content
        else:
            response.append(processed_chunk)
    return response
