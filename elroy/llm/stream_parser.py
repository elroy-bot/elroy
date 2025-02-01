import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator, Generic, Iterator, List, Optional, TypeVar, Union

from litellm.types.utils import Delta, ModelResponse

from ..config.llm import ChatModel
from ..db.db_models import FunctionCall
from .tool_call_accumulator import OpenAIToolCallAccumulator


@dataclass
class TextOutput(ABC):
    content: str


class AssistantInternalThought(TextOutput):
    content: str


class AssistantResponse(TextOutput):
    content: str


class AssistantToolResult(TextOutput):
    content: str


class SystemMessage(TextOutput):
    content: str


class SystemWarning(TextOutput):
    content: str


def to_openai_tool_call(content: str) -> Optional[FunctionCall]:
    try:
        d = json.loads(content)
        if d.get("name") and d.get("arguments"):
            return FunctionCall(id=uuid.uuid4().hex, function_name=d["name"], arguments=d["arguments"])
    except Exception:
        pass


@dataclass
class TagSet:
    keyword: str

    def begin_tag(self) -> str:
        return f"<{self.keyword}>"

    def end_tag(self) -> str:
        return f"</{self.keyword}>"


T = TypeVar("T", bound=Union[TextOutput, FunctionCall])


class TextProcessor(ABC, Generic[T]):
    tags: List[TagSet]

    def __init__(self):
        self.buffer = ""
        self.active_tag = None

    def is_active(self) -> bool:
        return self.active_tag is not None

    def activate(self, tag_keyword: str):
        self.active_tag = next(tag for tag in self.tags if tag.keyword == tag_keyword)

    def deactivate(self) -> None:
        assert len(self.buffer) == 0
        self.active_tag = None

    def process(self, text: str) -> Generator[T, None, None]:
        assert self.active_tag
        assert len(text) == 1
        self.buffer += text

        if not text.isspace():
            while self.buffer:
                if self.buffer.lstrip().endswith(self.active_tag.end_tag()):
                    self.buffer = self.buffer[: -len(self.buffer)].lstrip()
                    yield from self.flush()
                    self.deactivate()
                    return
                elif self.active_tag.end_tag().startswith(self.buffer.lstrip()):
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
    tags: List[TagSet] = [TagSet("internal_thought"), TagSet("think")]
    first_non_whitespace_emitted: bool = False

    def activate(self, tag_keyword: str):
        super().activate(tag_keyword)
        self.first_non_whitespace_emitted = False

    def maybe_consume_buffer(self) -> Generator[AssistantInternalThought, None, None]:
        if self.first_non_whitespace_emitted:
            yield AssistantInternalThought(self.buffer)
            self.buffer = ""
        elif not self.buffer.isspace():
            self.first_non_whitespace_emitted = True
            resp = AssistantInternalThought(self.buffer.lstrip())
            self.buffer = ""
            yield resp

        else:
            # Ignore leading whitespace
            pass

    def flush(self) -> Generator[AssistantInternalThought, None, None]:
        if self.buffer:
            yield AssistantInternalThought(self.buffer)
        self.deactivate()


class InlineToolCallProcessor(TextProcessor[FunctionCall]):
    tags = [TagSet("tool_call")]

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
                yield tool_call
        else:
            logging.warning("Buffer not empty, but cannot be converted to tool call")
        self.buffer = ""
        self.deactivate()


class StreamTextProcessor:
    def __init__(self):
        self.processors: List[TextProcessor] = [
            InlineToolCallProcessor(),
            InternalThoughtProcessor(),
        ]
        self.buffer = ""

        self.active_processor: Optional[TextProcessor] = None

    def process(self, text: str) -> Generator[Union[TextOutput, FunctionCall], None, None]:
        for char in text:
            self.buffer += char
            yield from self.process_buffer()

    def process_buffer(self) -> Generator[Union[TextOutput, FunctionCall], None, None]:
        while len(self.buffer) > 0:
            if self.active_processor:
                yield from self.active_processor.process(self.buffer[0])
                self.buffer = self.buffer[1:]
                if not self.active_processor.is_active():
                    self.active_processor = None
            else:
                partial_tag_match_found = False
                for processor in self.processors:
                    assert not processor.is_active(), "unexpeted active stream processor"

                    for tag in processor.tags:
                        if tag.begin_tag() == self.buffer:
                            self.active_processor = processor
                            self.active_processor.activate(tag.keyword)
                            self.buffer = ""
                            break
                        elif tag.begin_tag().startswith(self.buffer):
                            partial_tag_match_found = True
                if partial_tag_match_found:
                    # We should not consume the buffer, we may have started a tag but not finished it"""
                    return
                else:
                    if len(self.buffer) > 0:
                        yield AssistantResponse(self.buffer[0])
                        self.buffer = self.buffer[1:]

    def flush(self) -> Generator[Union[TextOutput, FunctionCall], None, None]:
        if self.buffer:
            if self.active_processor:
                yield from self.active_processor.flush()
            else:
                yield AssistantResponse(self.buffer)
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

    def process_stream(self) -> Generator[Union[TextOutput, FunctionCall], None, None]:
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

    def collect(self) -> List[Union[TextOutput, FunctionCall]]:
        response = []
        for processed_chunk in self.process_stream():
            if isinstance(processed_chunk, TextOutput):
                if len(response) == 0 or not type(response[-1]) == type(processed_chunk):
                    response.append(processed_chunk)
                else:
                    response[-1].content += processed_chunk.content
            else:
                response.append(processed_chunk)
        return response

    def get_full_text(self):
        return self.raw_text
