import json
from pathlib import Path

from toolz import pipe
from toolz.curried import map

from elroy.core.configs import ToolConfig
from elroy.core.constants import ASSISTANT, SYSTEM, TOOL, USER, tool
from elroy.core.ctx import ElroyConfig
from elroy.core.session import open_turn_context
from elroy.db.db_models import ToolCall
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.factory import build_context_refresh_orchestrator
from elroy.repository.context_messages.session import build_context_message_session
from elroy.tools.filesystem import ls, pwd, read_file
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


def test_infinite_tool_call_ends(ctx: ElroyConfig):
    ctx.debug = False

    ctx.tool_registry.register(get_secret_test_answer)

    process_test_message(
        ctx,
        "Please use the get_secret_test_answer to get the secret answer. The answer is not always available, so you may have to retry. Never give up, no matter how long it takes!",
    )

    # Not the most direct test, as the failure case is an infinite loop. However, if the test completes, it is a success.


def test_missing_tool_message_recovers(ctx: ElroyConfig):
    """
    Tests recovery when an assistant message is included without the corresponding subsequent tool message.
    """

    ctx.debug = False

    with open_turn_context(ctx) as turn:
        build_context_refresh_orchestrator(build_context_message_session(turn)).add_context_messages(_missing_tool_message(ctx))

    process_test_message(ctx, "Tell me more!")
    assert True  # ie, no error is raised


def test_missing_tool_call_recovers(ctx: ElroyConfig):
    """
    Tests recovery when a tool message is included without the corresponding assistant message with tool_calls.
    """

    ctx.debug = False

    with open_turn_context(ctx) as turn:
        build_context_refresh_orchestrator(build_context_message_session(turn)).add_context_messages(_missing_tool_call(ctx))

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


def test_exclude_tools(ctx: ElroyConfig):
    # Create new ElroyConfig with modified tool config
    new_tool_config = ToolConfig(
        custom_tools_path=ctx.tool_config.custom_tools_path,
        exclude_tools=["get_user_preferred_name"],
        allowed_shell_command_prefixes=ctx.tool_config.allowed_shell_command_prefixes,
        include_base_tools=ctx.tool_config.include_base_tools,
        shell_commands=ctx.tool_config.shell_commands,
    )

    new_ctx = ElroyConfig(
        database_url=ctx.database_url,
        chroma_path=ctx.chroma_path,
        model_config=ctx.model_config,
        ui_config=ctx.ui_config,
        memory_config=ctx.memory_config,
        tool_config=new_tool_config,
        runtime_config=ctx.runtime_config,
    )

    assert new_ctx.tool_registry.get("get_user_preferred_name") is None


def test_custom_tool(ctx: ElroyConfig):
    ctx.tool_registry.register(netflix_show_fetcher)
    response = process_test_message(ctx, "Please use your function to fetch the specified netflix show.")
    assert "Black Dove" in response


def test_langchain_tool(ctx: ElroyConfig):
    ctx.tool_registry.register(get_user_token_first_letter)
    process_test_message(ctx, "Please use your function to fetch the first letter of the user's token.")


def test_base_model_tool(ctx: ElroyConfig):
    ctx.tool_registry.register(get_game_info)

    process_test_message(ctx, "Please use your function to fetch the game info.")


def test_pwd_uses_current_working_directory(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)

    assert pwd() == str(tmp_path)


def test_ls_recurses_with_entry_cap(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    project_dir = tmp_path / "project"
    nested_dir = project_dir / "nested"
    nested_dir.mkdir(parents=True)
    (project_dir / "a.txt").write_text("a")
    (project_dir / "b.txt").write_text("b")
    (nested_dir / "c.txt").write_text("c")
    (nested_dir / "d.txt").write_text("d")

    result = ls("project", max_entries=3, max_depth=2)

    assert result.path == "project"
    assert result.type == "dir"
    assert result.recursive is True
    assert result.truncated is True
    assert [entry.path for entry in result.entries] == ["project/nested", "project/nested/c.txt", "project/nested/d.txt"]


def test_ls_returns_file_metadata_for_files(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "notes.txt"
    file_path.write_text("hello")

    result = ls("notes.txt")

    assert result.type == "file"
    assert result.recursive is False
    assert result.truncated is False
    assert len(result.entries) == 1
    assert result.entries[0].path == "notes.txt"
    assert result.entries[0].size_bytes == 5


def test_read_file_defaults_to_bounded_slice(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "sample.txt"
    file_path.write_text("\n".join(f"line {idx}" for idx in range(1, 206)))

    result = read_file("sample.txt")

    assert result.path == "sample.txt"
    assert result.start_line == 1
    assert result.end_line == 200
    assert result.total_lines == 205
    assert result.truncated is True
    assert result.content.splitlines()[0] == "1: line 1"
    assert result.content.splitlines()[-1] == "200: line 200"


def test_read_file_respects_requested_line_range(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\nbeta\ngamma\ndelta")

    result = read_file("sample.txt", start_line=2, end_line=3)

    assert result.start_line == 2
    assert result.end_line == 3
    assert result.total_lines == 4
    assert result.truncated is True
    assert result.content == "2: beta\n3: gamma"


def _missing_tool_message(ctx: ElroyConfig):
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


def _missing_tool_call(ctx: ElroyConfig) -> list[ContextMessage]:
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
