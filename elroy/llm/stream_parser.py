import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator, Generic, Iterator, Optional, Type, TypeVar, Union

from litellm.types.utils import Delta, ModelResponse

from ..config.config import ChatModel
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


class InlineToolCall(TextOutput):
    content: str


def to_openai_tool_call(content: str) -> Optional[FunctionCall]:
    try:
        d = json.loads(content)
        if d.get("name") and d.get("arguments"):
            return FunctionCall(id=uuid.uuid4().hex, function_name=d["name"], arguments=d["arguments"])
    except Exception:
        pass


T = TypeVar("T", bound=TextOutput)


class TextAccumulator(Generic[T]):
    def __init__(self, output_type: Type[T], opening_tag: str, closing_tag: str):
        self.output_type = output_type
        self.opening_tag = opening_tag
        self.closing_tag = closing_tag

        self.is_active = False
        self.is_first_output_chunk_emitted = None
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

        while self.buffer:
            if self.buffer.isspace():
                break
            elif self.is_active:
                if self.closing_tag in self.buffer:
                    text_before_tag, text_after_tag = self.buffer.split(self.closing_tag, maxsplit=1)

                    if text_before_tag and not text_before_tag.isspace():  # if we have non-space text before the closing tag
                        if not self.is_first_output_chunk_emitted:
                            content = text_before_tag.strip()
                            self.is_first_output_chunk_emitted = True
                        else:
                            content = text_before_tag.rstrip()
                        yield self.output_type(content)
                    self.is_active = False
                    self.buffer = text_after_tag
                    self.is_first_output_chunk_emitted = None
                elif self._has_possible_tag_fragment(self.buffer, self.closing_tag):
                    break
                else:
                    if not self.is_first_output_chunk_emitted:
                        content = self.buffer.lstrip()
                        self.is_first_output_chunk_emitted = True
                    else:
                        content = self.buffer
                    yield self.output_type(content)
                    self.buffer = ""
            else:
                if self.opening_tag in self.buffer:
                    self.is_active = True
                    self.is_first_output_chunk_emitted = False
                    text_before_tag, text_after_tag = self.buffer.split(self.opening_tag, maxsplit=1)

                    if text_before_tag:
                        yield text_before_tag.rstrip()
                    self.buffer = text_after_tag

                elif self._has_possible_tag_fragment(self.buffer, self.opening_tag):
                    break
                else:
                    yield self.buffer
                    self.buffer = ""

    def _has_possible_tag_fragment(self, text: str, tag: str) -> bool:
        if tag in text:
            raise ValueError("This function only intended to capture partial matches, a full match indicates a bug")

        while tag[0] in text:
            text = text[text.index(tag[0]) :]

            if tag.startswith(text[: len(tag)]):
                return True
            else:
                text = text[1:]
        return False

    def flush(self) -> Generator[Union[T, str], None, None]:
        if self.buffer:
            yield self.buffer
            self.buffer = ""
            self.is_active = False


class TextProcessor(ABC):
    def __init__(self, next_processor: Optional["TextProcessor"] = None):
        self.next_processor = next_processor

    @abstractmethod
    def process(self, text: str) -> Generator[Union[TextOutput, FunctionCall], None, None]:
        pass

    def process_next(self, text: str) -> Generator[Union[TextOutput, FunctionCall], None, None]:
        if self.next_processor:
            yield from self.next_processor.process(text)
        else:
            yield AssistantResponse(text)

    def flush(self) -> Generator[Union[TextOutput, FunctionCall], None, None]:
        if self.next_processor:
            yield from self.next_processor.flush()


class InternalThoughtProcessor(TextProcessor):
    def __init__(self, next_processor: Optional[TextProcessor] = None):
        super().__init__(next_processor)
        self.accumulator = TextAccumulator(AssistantInternalThought, "<internal_thought>", "</internal_thought>")

    def process(self, text: str) -> Generator[Union[TextOutput, FunctionCall], None, None]:
        for processed_text in self.accumulator.update(text):
            if isinstance(processed_text, AssistantInternalThought):
                yield processed_text
            else:
                yield from self.process_next(processed_text)

    def flush(self) -> Generator[Union[TextOutput, FunctionCall], None, None]:
        for processed_text in self.accumulator.flush():
            if isinstance(processed_text, AssistantInternalThought):
                yield processed_text
            else:
                yield from self.process_next(processed_text)
        if self.next_processor:
            yield from self.next_processor.flush()


# TODO: This needs update needs to be handled differently, we must accumulate all the text from the accumulator until we have a function call, then yield.
class InlineToolCallProcessor(TextProcessor):
    def __init__(self, next_processor: Optional[TextProcessor] = None):
        super().__init__(next_processor)
        self.accumulator = TextAccumulator(InlineToolCall, "<tool_call>", "</tool_call>")
        self.tool_call_text = ""

    def process(self, text: str) -> Generator[Union[TextOutput, FunctionCall], None, None]:
        for processed_text in self.accumulator.update(text):
            if isinstance(processed_text, InlineToolCall):
                self.tool_call_text += processed_text.content
                tool_call = to_openai_tool_call(self.tool_call_text)
                if tool_call:
                    yield tool_call
                    self.tool_call_text = ""
            else:
                yield from self.process_next(processed_text)


class StreamParser:
    def __init__(self, chat_model: ChatModel, chunks: Iterator[ModelResponse]):
        self.chunks = chunks
        self.openai_tool_call_accumulator = OpenAIToolCallAccumulator(chat_model)
        # Chain the processors
        self.text_processor = InternalThoughtProcessor(InlineToolCallProcessor())
        self.raw_text = None

    def process(self) -> Generator[Union[TextOutput, FunctionCall], None, None]:
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
                yield from self.process_text_chunk(text)
        yield from self.text_processor.flush()

    def get_full_text(self):
        return self.raw_text

    def process_text_chunk(self, text: str) -> Generator[Union[TextOutput, FunctionCall], None, None]:
        yield from self.text_processor.process(text)
