import json

import pytest
from scripts.release_patch import get_function_schemas
from tests.utils import process_test_message
from toolz import pipe
from toolz.curried import map

from elroy.config.constants import (
    ASSISTANT,
    SYSTEM,
    TOOL,
    USER,
    MissingAssistantToolCallError,
    MissingToolCallMessageError,
)
from elroy.config.ctx import ElroyContext
from elroy.repository.data_models import ContextMessage, ToolCall
from elroy.repository.message import add_context_messages


def test_infinite_tool_call_ends(ctx: ElroyContext):
    ctx.debug = False

    process_test_message(
        ctx,
        "Please use the get_secret_test_answer to get the secret answer. The answer is not always available, so you may have to retry. Never give up, no matter how long it takes!",
    )

    # Not the most direct test, as the failure case is an infinite loop. However, if the test completes, it is a success.


def test_missing_tool_message_recovers(ctx: ElroyContext):
    """
    Tests recovery when an assistant message is included without the corresponding subsequent tool message.
    """

    ctx.debug = False

    add_context_messages(ctx, _missing_tool_message(ctx))

    process_test_message(ctx, "Tell me more!")
    assert True  # ie, no error is raised


def test_missing_tool_message_throws(ctx: ElroyContext):
    """
    Tests that an error is raised when an assistant message is included without the corresponding subsequent tool message.
    """

    ctx.debug = True

    add_context_messages(ctx, _missing_tool_message(ctx))

    with pytest.raises(MissingToolCallMessageError):
        process_test_message(ctx, "Tell me more!")


def test_missing_tool_call_recovers(ctx: ElroyContext):
    """
    Tests recovery when a tool message is included without the corresponding assistant message with tool_calls.
    """

    ctx.debug = False

    add_context_messages(ctx, _missing_tool_call(ctx))

    process_test_message(ctx, "Tell me more!")
    assert True  # ie, no error is raised


def test_missing_tool_call_throws(ctx: ElroyContext):
    """
    Tests that an error is raised when a tool message is included without the corresponding assistant message with tool_calls.
    """

    ctx.debug = True

    add_context_messages(ctx, _missing_tool_call(ctx))

    with pytest.raises(MissingAssistantToolCallError):
        process_test_message(ctx, "Tell me more!")


def test_tool_schema_does_not_have_elroy_ctx():

    argument_names = pipe(
        get_function_schemas(),
        map(lambda x: (x["function"]["name"], list(x["function"]["parameters"]["properties"].keys()))),
        dict,
    )

    assert not any("ctx" in vals for key, vals in argument_names.items())  # type: ignore


def _missing_tool_message(ctx: ElroyContext):
    return [
        ContextMessage(
            role=USER,
            content="Hello! My name is George. I'm curious about the history of Minnesota. Can you tell me about it?",
            chat_model=None,
        ),
        ContextMessage(
            role=ASSISTANT,
            content="Hello George! It's nice to meet you. I'd be happy to share some information about the history of Minnesota with you. What aspect of Minnesota's history are you most interested in?",
            chat_model=ctx.chat_model.name,
            tool_calls=[  # missing subsequent tool message
                ToolCall(
                    id="abc",
                    function={"name": "get_user_preferred_name", "arguments": json.dumps([])},
                )
            ],
        ),
    ]


def _missing_tool_call(ctx: ElroyContext):
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
            chat_model=ctx.chat_model.name,
            tool_calls=None,
        ),
        ContextMessage(  # previous message missing tool_calls
            role=TOOL,
            content="George",
            tool_call_id="abc",
            chat_model=ctx.chat_model.name,
        ),
    ]
