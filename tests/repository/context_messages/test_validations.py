import pytest
from elroy.config.constants import ASSISTANT, SYSTEM, TOOL, USER
from elroy.db.db_models import ToolCall
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.validations import Validator


def test_assistant_tool_calls_followed_by_tool(ctx):
    """Test that assistant messages with tool calls must be followed by tool messages"""
    messages = [
        ContextMessage(role=SYSTEM, content="system message", chat_model=None),
        ContextMessage(role=USER, content="user message", chat_model=None),
        ContextMessage(
            role=ASSISTANT,
            content="assistant message",
            chat_model=None,
            tool_calls=[ToolCall(id="123", name="test_tool", arguments='{"arg": "value"}')],
        ),
    ]

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())

    assert len(validated) == 3
    assert validated[2].tool_calls is None
    assert "Assistant message with tool_calls not followed by tool message" in validator.errors[0]


def test_tool_messages_have_assistant_tool_call(ctx):
    """Test that tool messages must have a preceding assistant message with matching tool call"""
    messages = [
        ContextMessage(role=SYSTEM, content="system message", chat_model=None),
        ContextMessage(role=USER, content="user message", chat_model=None),
        ContextMessage(role=TOOL, content="tool response", chat_model=None, tool_call_id="123"),
    ]

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())

    assert len(validated) == 2
    assert "Tool message without preceding assistant message with tool_calls" in validator.errors[0]


def test_system_instruction_correctly_placed(ctx):
    """Test that system message must be first and only first"""
    messages = [
        ContextMessage(role=USER, content="user message", chat_model=None),
        ContextMessage(role=SYSTEM, content="system message", chat_model=None),
    ]

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())

    assert len(validated) == 2
    assert validated[0].role == SYSTEM
    assert validated[1].role == USER
    assert "First message is not system instruction" in validator.errors[0]


def test_first_user_precedes_first_assistant(ctx):
    """Test that first non-system message must be from user"""
    messages = [
        ContextMessage(role=SYSTEM, content="system message", chat_model=None),
        ContextMessage(role=ASSISTANT, content="assistant message", chat_model=None),
    ]

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())

    assert len(validated) == 3
    assert validated[0].role == SYSTEM
    assert validated[1].role == USER
    assert validated[2].role == ASSISTANT
    assert "First non-system message is not user message" in validator.errors[0]


def test_valid_message_sequence(ctx):
    """Test that a valid message sequence passes validation without changes"""
    messages = [
        ContextMessage(role=SYSTEM, content="system message", chat_model=None),
        ContextMessage(role=USER, content="user message", chat_model=None),
        ContextMessage(
            role=ASSISTANT,
            content="assistant message",
            chat_model=None,
            tool_calls=[ToolCall(id="123", name="test_tool", arguments='{"arg": "value"}')],
        ),
        ContextMessage(role=TOOL, content="tool response", chat_model=None, tool_call_id="123"),
    ]

    validator = Validator(ctx, messages)
    validated = list(validator.validated_msgs())

    assert len(validated) == len(messages)
    assert len(validator.errors) == 0
    assert [m.role for m in validated] == [m.role for m in messages]
