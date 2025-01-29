from typing import List

import pytest

from elroy.config.constants import Provider
from elroy.config.llm import ChatModel
from elroy.db.db_models import FunctionCall
from elroy.llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    StreamParser,
    TextOutput,
)

CHAT_MODEL = ChatModel(
    name="foo",
    enable_caching=True,
    api_key="abc",
    provider=Provider.OTHER,
    ensure_alternating_roles=False,
    inline_tool_calls=True,
)


def parse(chunks: List[str]) -> List[TextOutput]:
    parser = StreamParser(CHAT_MODEL, iter([]))
    output = []
    for chunk in chunks:
        for processed_chunk in parser.process_text_chunk(chunk):
            if isinstance(processed_chunk, FunctionCall):
                output.append(processed_chunk)

            elif not output:
                output.append(processed_chunk)
            elif type(output[-1]) == type(processed_chunk):
                output[-1].content += processed_chunk.content  # type: ignore
            else:
                output.append(processed_chunk)
    return output


def test_complete_tag_in_single_chunk():
    assert parse(["<internal_thought>This is a thought</internal_thought>Some normal text"]) == [
        AssistantInternalThought(content="This is a thought"),
        AssistantResponse(content="Some normal text"),
    ]


def test_tag_split_across_chunks():
    assert parse(["<internal_th", "ought>This is a thought</inte", "rnal_thought>Some normal text."]) == [
        AssistantInternalThought(content="This is a thought"),
        AssistantResponse(content="Some normal text."),
    ]


def test_single_char_chunks():
    assert parse(list("<internal_thought>This is a thought</internal_thought>Some normal text.")) == [
        AssistantInternalThought(content="This is a thought"),
        AssistantResponse(content="Some normal text."),
    ]


def test_no_tags():
    assert parse(list("Just some normal text with no special tags.")) == [AssistantResponse("Just some normal text with no special tags.")]


def test_hanging_tags():
    assert parse(list("<internal_thou>This is a thought")) == [AssistantResponse("<internal_thou>This is a thought")]


@pytest.mark.skip("Need to solve edge case around flushing")
def test_tricky_tags():
    response = parse(list("<<internal_thought>>This is a thought</internal_thought><Some normal text."))

    assert response == [
        AssistantResponse("<"),
        AssistantInternalThought(">This is a thought"),
        AssistantResponse("<Some normal text."),
    ]


def test_unknown_tags():
    assert parse(["<unknown_tag>", "Should be treated as normal text", "</unknown_tag>"]) == [
        AssistantResponse("<unknown_tag>Should be treated as normal text</unknown_tag>")
    ]


def test_interleaved_tags_and_text():
    assert parse(
        [
            "<internal_thought>Tho",
            "ught 1</i",
            "nternal_thought>",
            "Normal text ",
            "<internal_thought>Thought 2</internal_thought>",
            "More text",
        ]
    ) == [
        AssistantInternalThought("Thought 1"),
        AssistantResponse("Normal text "),
        AssistantInternalThought("Thought 2"),
        AssistantResponse("More text"),
    ]


def test_incomplete_tags():
    assert parse(["<internal_thought>This is a thought", " and it continues"]) == [
        AssistantInternalThought("This is a thought and it continues")
    ]


def test_misnested_tags():
    assert parse(["<internal_thought><internal_thought>Some text</another_tag></internal_thought>"]) == [
        AssistantInternalThought("<internal_thought>Some text</another_tag>")
    ]


def test_inline_tool_call():
    input = """<tool_call>{
    "arguments": {
        "name": "Receiving instructions for tool calling",
        "text": "Today I learned how to call tools in Elroy."
    },
    "name": "create_memory"
}</tool_call>"""
    output = parse([input])
    assert len(output) == 1
    assert isinstance(output[0], FunctionCall)


def test_inline_tool_call_iter():
    input = """<tool_call>{
    "arguments": {
        "name": "Receiving instructions for tool calling",
        "text": "Today I learned how to call tools in Elroy."
    },
    "name": "create_memory"
}</tool_call>"""
    output = parse(list(input))
    assert len(output) == 1
    assert isinstance(output[0], FunctionCall)


def test_internal_thought_and_tool():
    input = """<internal_thought> I should call a tool </internal_thought><tool_call>{
    "arguments": {
        "name": "Receiving instructions for tool calling",
        "text": "Today I learned how to call tools in Elroy."
    },
    "name": "create_memory"
}</tool_call>Did the tool call work?"""
    output = parse([input])
    assert len(output) == 3

    assert output[0] == AssistantInternalThought("I should call a tool")
    assert isinstance(output[1], FunctionCall)
    assert output[2] == AssistantResponse("Did the tool call work?")


def test_internal_thought_and_tool_iter():
    input = """<internal_thought> I should call a tool </internal_thought><tool_call>{
    "arguments": {
        "name": "Receiving instructions for tool calling",
        "text": "Today I learned how to call tools in Elroy."
    },
    "name": "create_memory"
}</tool_call>Did the tool call work?"""
    output = parse(list(input))
    assert len(output) == 3

    assert output[0] == AssistantInternalThought("I should call a tool")
    assert isinstance(output[1], FunctionCall)
    assert output[2] == AssistantResponse("Did the tool call work?")
