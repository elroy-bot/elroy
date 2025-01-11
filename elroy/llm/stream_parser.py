from abc import ABC
from dataclasses import dataclass
from typing import Generator, Generic, Iterator, Type, TypeVar, Union

from litellm.types.utils import Delta, ModelResponse

from ..config.config import ChatModel
from ..db.db_models import FunctionCall
from .tool_call_accumulator import ToolCallAccumulator


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


T = TypeVar("T", bound=TextOutput)


class TextAccumulator(Generic[T]):
    def __init__(self, output_type: Type[T], opening_tag: str, closing_tag: str):
        self.output_type = output_type
        self.opening_tag = opening_tag
        self.closing_tag = closing_tag

        self.is_active = False
        self.buffer = ""

    def update(self, content_chunk: str) -> Generator[Union[T, str], None, None]:
        # Accepts text as input, one or more characters at a time.
        # If not active:
        #   # if the accumulated text might contain the beginning of the opening tag, accumulate text
        #   # if the accumulated text no longer can match the opening tag, yield the accumulated text as a string
        #   # if the accumulated text matches the opening tag, set is_active to True, and yield any text that follows the opening tag as AssistantInternalThought
        # If active:
        #   # if the accumulated text might contain the beginning of the closing tag, accumulate text
        #   # if the accumulated text no longer can match the closing tag, yield the accumulated text as a string
        #   # if the accumulated text matches the closing tag, set is_active to False, and yield any text that precedes the closing tag as AssistantInternalThought, yield any text that follows the closing tag as a string
        self.buffer += content_chunk
        if self.is_active:
            if self.closing_tag in self.buffer:
                text_before_tag = self.buffer[: self.buffer.index(self.closing_tag)].rstrip()
                if text_before_tag:
                    yield self.output_type(text_before_tag)
                text_after_tag = self.buffer[self.buffer.index(self.closing_tag) + len(self.closing_tag) :].lstrip()
                if text_after_tag:
                    yield text_after_tag
                self.is_active = False
                self.buffer = ""
            elif self.closing_tag[0] in self.buffer:
                # check if closing tag starts with text at < and after:
                possible_closing_tag_start = self.buffer[self.buffer.index("<") :]
                if self.closing_tag.startswith(possible_closing_tag_start):
                    text_before_possible_tag = self.buffer[: self.buffer.index("<")].strip()
                    if text_before_possible_tag:
                        yield self.output_type(text_before_possible_tag)
                        self.buffer = self.buffer[self.buffer.index("<") :]
                else:
                    first_char, remaining = self.buffer[0], self.buffer[1:]
                    self.buffer = ""
                    yield self.output_type(first_char)
                    yield from self.update(remaining)
            else:
                yield self.output_type(self.buffer)
                self.buffer = ""
        else:
            if self.opening_tag in self.buffer:
                self.is_active = True
                text_before_tag = self.buffer[: self.buffer.index(self.opening_tag)].rstrip()
                if text_before_tag:
                    yield text_before_tag
                text_after_tag = self.buffer[self.buffer.index(self.opening_tag) + len(self.opening_tag) :].lstrip()
                self.buffer = ""
                if text_after_tag:
                    yield from self.update(text_after_tag)
            elif self.opening_tag[0] in self.buffer:
                # check if opening tag starts with text at < and after:
                possible_opening_tag_start = self.buffer[self.buffer.index("<") :]
                if self.opening_tag.startswith(possible_opening_tag_start):
                    text_before_possible_tag = self.buffer[: self.buffer.index("<")]
                    if text_before_possible_tag:
                        yield text_before_possible_tag
                        self.buffer = self.buffer[self.buffer.index("<") :]
                else:
                    first_char, remaining = self.buffer[0], self.buffer[1:]
                    self.buffer = ""
                    yield first_char
                    yield from self.update(remaining)
            else:
                yield self.buffer
                self.buffer = ""

    def flush(self) -> Generator[Union[T, str], None, None]:
        if self.buffer:
            yield self.buffer
            self.buffer = ""
            self.is_active = False


class StreamParser:
    def __init__(self, chat_model: ChatModel, chunks: Iterator[ModelResponse]):
        self.chunks = chunks
        self.buffer = ""
        self.tool_call_accumulator = ToolCallAccumulator(chat_model)
        self.internal_thought_accumulator = TextAccumulator(AssistantInternalThought, "<internal_thought>", "</internal_thought>")
        self.accumulated_text = ""
        self.allowed_tags = {"internal_thought"}
        self.raw_text = None

    def process(self) -> Generator[Union[AssistantResponse, AssistantInternalThought, FunctionCall], None, None]:
        for chunk in self.chunks:
            delta = chunk.choices[0].delta  # type: ignore
            assert isinstance(delta, Delta)
            if delta.tool_calls:
                yield from self.tool_call_accumulator.update(delta.tool_calls)
            if delta.content:
                text = delta.content
                if not self.raw_text:
                    self.raw_text = text
                else:
                    self.raw_text += text
                assert isinstance(text, str)
                yield from self.process_text_chunk(text)

    def get_full_text(self):
        return self.raw_text

    def process_text_chunk(self, text: str) -> Generator[Union[AssistantResponse, AssistantInternalThought, FunctionCall], None, None]:
        for processed_text in self.internal_thought_accumulator.update(text):
            if isinstance(processed_text, AssistantInternalThought):
                yield processed_text
            else:
                yield AssistantResponse(processed_text)
