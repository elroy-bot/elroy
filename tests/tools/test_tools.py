import json

import pytest
from tests.utils import process_test_message

from elroy.config.config import ElroyContext
from elroy.config.constants import (
    ASSISTANT,
    SYSTEM,
    TOOL,
    USER,
    MissingAssistantToolCallError,
    MissingToolCallMessageError,
)
from elroy.repository.data_models import ContextMessage, ToolCall
from elroy.repository.message import add_context_messages


def test_missing_tool_message_recovers(elroy_context: ElroyContext):
    """
    Tests recovery when an assistant message is included without the corresponding subsequent tool message.
    """

    elroy_context.config.debug_mode = False

    add_context_messages(elroy_context, _missing_tool_message(elroy_context))

    process_test_message(elroy_context, "Tell me more!")
    assert True  # ie, no error is raised


def test_missing_tool_message_throws(elroy_context: ElroyContext):
    """
    Tests that an error is raised when an assistant message is included without the corresponding subsequent tool message.
    """

    elroy_context.config.debug_mode = True

    add_context_messages(elroy_context, _missing_tool_message(elroy_context))

    with pytest.raises(MissingToolCallMessageError):
        process_test_message(elroy_context, "Tell me more!")


def test_missing_tool_call_recovers(elroy_context: ElroyContext):
    """
    Tests recovery when a tool message is included without the corresponding assistant message with tool_calls.
    """

    elroy_context.config.debug_mode = False

    add_context_messages(elroy_context, _missing_tool_call(elroy_context))

    process_test_message(elroy_context, "Tell me more!")
    assert True  # ie, no error is raised


def test_missing_tool_call_throws(elroy_context: ElroyContext):
    """
    Tests that an error is raised when a tool message is included without the corresponding assistant message with tool_calls.
    """

    elroy_context.config.debug_mode = True

    add_context_messages(elroy_context, _missing_tool_call(elroy_context))

    with pytest.raises(MissingAssistantToolCallError):
        process_test_message(elroy_context, "Tell me more!")


def _missing_tool_message(elroy_context: ElroyContext):
    return [
        ContextMessage(
            role=USER,
            content="Hello! My name is George. I'm curious about the history of Minnesota. Can you tell me about it?",
            chat_model=None,
        ),
        ContextMessage(
            role=ASSISTANT,
            content="Hello George! It's nice to meet you. I'd be happy to share some information about the history of Minnesota with you. What aspect of Minnesota's history are you most interested in?",
            chat_model=elroy_context.config.chat_model.name,
            tool_calls=[  # missing subsequent tool message
                ToolCall(
                    id="abc",
                    function={"name": "get_user_preferred_name", "arguments": json.dumps([])},
                )
            ],
        ),
    ]


def _missing_tool_call(elroy_context: ElroyContext):
    return [
        ContextMessage(
            role=SYSTEM,
            content="You are a helpful assistant",
            chat_model=None,
        ),
        ContextMessage(
            role=USER,
            content="Hello! My name is George. I'm curious about the history of Minnesota. Can you tell me about it?",
            chat_model=None,
        ),
        ContextMessage(
            role=ASSISTANT,
            content="Hello George! It's nice to meet you. I'd be happy to share some information about the history of Minnesota with you. What aspect of Minnesota's history are you most interested in?",
            chat_model=elroy_context.config.chat_model.name,
            tool_calls=None,
        ),
        ContextMessage(  # previous message missing tool_calls
            role=TOOL,
            content="George",
            tool_call_id="abc",
            chat_model=elroy_context.config.chat_model.name,
        ),
    ]
