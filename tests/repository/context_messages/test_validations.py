import uuid

import pytest

from elroy.core.constants import ASSISTANT, SYSTEM, SYSTEM_INSTRUCTION_LABEL, TOOL, USER
from elroy.db.db_models import ToolCall
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.operations import replace_context_messages
from elroy.repository.context_messages.queries import get_context_messages
from elroy.repository.context_messages.transforms import is_system_instruction
from elroy.repository.context_messages.validations import Validator


def test_assistant_tool_calls_followed_by_tool(ctx, system_instruct, tool_call):
    """Test that assistant messages with tool calls must be followed by tool messages"""
    replace_context_messages(
        ctx,
        [
            system_instruct,
            ContextMessage(role=USER, content="user message", chat_model=None),
            ContextMessage(
                role=ASSISTANT,
                content="assistant message",
                chat_model=None,
                tool_calls=[tool_call],
            ),
        ],
    )
    messages = get_context_messages(ctx)

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())

    assert len(validated) == 3
    assert validated[2].tool_calls is None
    assert "Last message is assistant" in validator.errors[0]
    fetched_ids = [m.id for m in get_context_messages(ctx)]

    assert fetched_ids != [m.id for m in messages]
    assert fetched_ids == [m.id for m in validated]


def test_wrong_tool_call_id(ctx, system_instruct, tool_call: ToolCall, tool_call_2: ToolCall):

    messages = [
        system_instruct,
        ContextMessage(role=USER, content="user message", chat_model=None),
        ContextMessage(role=ASSISTANT, content="assistant message", chat_model=None, tool_calls=[tool_call, tool_call_2]),
        ContextMessage(role=TOOL, content="tool response", chat_model=None, tool_call_id=tool_call.id),
        ContextMessage(role=TOOL, content="tool response", chat_model=None, tool_call_id="wrong_id"),
    ]

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())
    assert len(validated) == 4  # wrong_id tool message is removed
    assert not any(msg.tool_call_id == "wrong_id" for msg in validated)
    assert any("without corresponding tool_message" in error for error in validator.errors)
    assert any("without preceding assistant message" in error for error in validator.errors)


def test_multiple_tool_calls(ctx, system_instruct, tool_call: ToolCall, tool_call_2: ToolCall):
    messages = [
        system_instruct,
        ContextMessage(role=USER, content="user message", chat_model=None),
        ContextMessage(role=ASSISTANT, content="assistant message", chat_model=None, tool_calls=[tool_call, tool_call_2]),
        ContextMessage(role=TOOL, content="tool response", chat_model=None, tool_call_id=tool_call.id),
        ContextMessage(role=TOOL, content="tool response", chat_model=None, tool_call_id=tool_call_2.id),
    ]

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())
    assert len(validated) == 5
    assert not validator.errors


def test_tool_messages_have_assistant_tool_call(ctx, system_instruct):
    """Test that tool messages must have a preceding assistant message with matching tool call"""
    messages = [
        system_instruct,
        ContextMessage(role=USER, content="user message", chat_model=None),
        ContextMessage(role=TOOL, content="tool response", chat_model=None, tool_call_id="123"),
    ]

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())

    assert len(validated) == 2
    assert "Tool message without preceding assistant message with tool_calls" in validator.errors[0]
    assert [m.id for m in get_context_messages(ctx)] == [m.id for m in validated]


def test_system_instruction_correctly_placed(ctx):
    """Test that system message must be first and only first"""
    raw_messages = [
        ContextMessage(role=USER, content="user message", chat_model=None),
        ContextMessage(role=SYSTEM, content="system message", chat_model=None),
    ]

    replace_context_messages(ctx, raw_messages)

    messages = get_context_messages(ctx)

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())

    assert len(validated) == 3
    assert validated[0].role == SYSTEM
    assert validated[1].role == USER
    assert "First message is not system instruction" in validator.errors[0]
    assert [m.id for m in get_context_messages(ctx)] == [m.id for m in validated]


def test_first_user_precedes_first_assistant(ctx, system_instruct):
    """Test that first non-system message must be from user"""

    ctx.chat_model.ensure_alternating_roles = True
    messages = [
        system_instruct,
        ContextMessage(role=ASSISTANT, content="assistant message", chat_model=None),
    ]

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())

    assert len(validated) == 3
    assert validated[0].role == SYSTEM
    assert validated[1].role == USER
    assert validated[2].role == ASSISTANT
    assert "First non-system message is not user message" in validator.errors[0]
    assert [m.id for m in get_context_messages(ctx)] == [m.id for m in validated]


def test_ignore_first_user_precedes_first_assistant(ctx, system_instruct):
    """Test that first non-system message must be from user"""

    ctx.chat_model.ensure_alternating_roles = False
    messages = [
        system_instruct,
        ContextMessage(role=ASSISTANT, content="assistant message", chat_model=None),
    ]

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())

    assert len(validated) == 2
    assert validated[0].role == SYSTEM
    assert validated[1].role == ASSISTANT
    assert not validator.errors


def test_valid_message_sequence(ctx, system_instruct, tool_call):
    """Test that a valid message sequence passes validation without changes"""
    messages = [
        system_instruct,
        ContextMessage(role=USER, content="user message", chat_model=None),
        ContextMessage(
            role=ASSISTANT,
            content="assistant message",
            chat_model=None,
            tool_calls=[tool_call],
        ),
        ContextMessage(role=TOOL, content="tool response", chat_model=None, tool_call_id=tool_call.id),
    ]

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())

    assert len(validated) == len(messages)
    assert len(validator.errors) == 0
    assert [m.role for m in validated] == [m.role for m in messages]


@pytest.fixture(scope="function")
def tool_call():
    return ToolCall(id=uuid.uuid4().hex, function={"name": "test_tool", "arguments": '{"arg": "value"}'})


@pytest.fixture(scope="function")
def tool_call_2():
    return ToolCall(id=uuid.uuid4().hex, function={"name": "test_tool", "arguments": '{"arg": "value"}'})


@pytest.fixture(scope="function")
def system_instruct():
    msg = ContextMessage(role=SYSTEM, content=SYSTEM_INSTRUCTION_LABEL + "system message", chat_model=None)
    assert is_system_instruction(msg)
    return msg
