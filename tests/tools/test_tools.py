import json

from toolz import pipe
from toolz.curried import map

from elroy.core.configs import ToolConfig
from elroy.core.constants import ASSISTANT, SYSTEM, TOOL, USER, tool
from elroy.core.ctx import ElroyContext
from elroy.db.db_models import ToolCall
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.operations import add_context_messages
from elroy.tools.registry import get_system_tool_schemas
from tests.fixtures.custom_tools import (
    get_game_info,
    get_user_token_first_letter,
    netflix_show_fetcher,
)
from tests.utils import process_test_message


@tool
def get_secret_test_answer() -> str:
    """Get the secret test answer

    Returns:
        str: the secret answer

    """
    return "I'm sorry, the secret answer is not available. Please try once more."


def test_infinite_tool_call_ends(ctx: ElroyContext):
    ctx.debug = False

    ctx.tool_registry.register(get_secret_test_answer)

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


def test_missing_tool_call_recovers(ctx: ElroyContext):
    """
    Tests recovery when a tool message is included without the corresponding assistant message with tool_calls.
    """

    ctx.debug = False

    add_context_messages(ctx, _missing_tool_call(ctx))

    process_test_message(ctx, "Tell me more!")
    assert True  # ie, no error is raised


def test_tool_schema_does_not_have_elroy_ctx():

    argument_names = pipe(
        get_system_tool_schemas(),
        map(
            lambda x: (
                x["function"]["name"],
                list(x["function"]["parameters"]["properties"].keys()) if "parameters" in x["function"] else [],
            )
        ),
        dict,
    )

    assert not any("ctx" in vals for key, vals in argument_names.items())


def test_exclude_tools(ctx: ElroyContext):
    # Create new ElroyContext with modified tool config
    new_tool_config = ToolConfig(
        custom_tools_path=ctx.tool_config.custom_tools_path,
        exclude_tools=["get_user_preferred_name"],
        allowed_shell_command_prefixes=ctx.tool_config.allowed_shell_command_prefixes,
        include_base_tools=ctx.tool_config.include_base_tools,
        shell_commands=ctx.tool_config.shell_commands,
    )

    new_ctx = ElroyContext(
        database_config=ctx.database_config,
        model_config=ctx.model_config,
        ui_config=ctx.ui_config,
        memory_config=ctx.memory_config,
        tool_config=new_tool_config,
        runtime_config=ctx.runtime_config,
    )

    assert new_ctx.tool_registry.get("get_user_preferred_name") is None


def test_custom_tool(ctx: ElroyContext):
    ctx.tool_registry.register(netflix_show_fetcher)
    response = process_test_message(ctx, "Please use your function to fetch the specified netflix show.")
    assert "Black Dove" in response


def test_langchain_tool(ctx: ElroyContext):
    ctx.tool_registry.register(get_user_token_first_letter)
    process_test_message(ctx, "Please use your function to fetch the first letter of the user's token.")


def test_base_model_tool(ctx: ElroyContext):
    ctx.tool_registry.register(get_game_info)

    process_test_message(ctx, "Please use your function to fetch the game info.")


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


def _missing_tool_call(ctx: ElroyContext) -> list[ContextMessage]:
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
