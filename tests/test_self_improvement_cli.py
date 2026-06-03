"""End-to-end tests for the self-improvement CLI flags.

Covers the full surface area needed to observe the self-improvement flow from
outside the process: listing loaded tools, listing loaded plugins, and
inspecting recorded Codex sessions.
"""

import json
from pathlib import Path

from elroy.core.session import open_turn_context
from elroy.db.db_models import CodexSession
from elroy.ui.app import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_tool_file(path: Path, func_name: str = "custom_contrib_tool") -> None:
    path.write_text(
        f"""\
from elroy.core.constants import tool


@tool
def {func_name}(msg: str) -> str:
    \"\"\"A generated contrib tool.

    Args:
        msg: Input message.
    \"\"\"
    return msg
""",
        encoding="utf-8",
    )


def _write_plugin_file(path: Path, plugin_name: str = "custom_panel", tab_label: str = "Custom") -> None:
    path.write_text(
        f"""\
from elroy.plugins.plugin import ElroyPlugin


def _make():
    from textual.widget import Widget
    return Widget()


ELROY_PLUGIN = ElroyPlugin(name={plugin_name!r}, tab_label={tab_label!r}, widget_factory=_make)
""",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# list-tools
# ---------------------------------------------------------------------------


def test_list_tools_returns_base_tools(capsys) -> None:
    main(["list-tools"])
    out = capsys.readouterr().out.strip()
    tools = json.loads(out)
    assert isinstance(tools, list)
    assert len(tools) > 0


def test_list_tools_no_base_tools_returns_empty_without_contrib(capsys) -> None:
    main(["list-tools", "--no-base-tools"])
    out = capsys.readouterr().out.strip()
    tools = json.loads(out)
    assert tools == []


def test_list_tools_discovers_contrib_tool(capsys, tmp_path: Path) -> None:
    contrib_dir = tmp_path / "contrib"
    contrib_dir.mkdir()
    _write_tool_file(contrib_dir / "mytools.py", func_name="my_e2e_tool")

    main(["list-tools", "--no-base-tools", "--contrib-tools-path", str(contrib_dir)])
    out = capsys.readouterr().out.strip()
    tools = json.loads(out)
    assert "my_e2e_tool" in tools


def test_list_tools_includes_base_and_contrib(capsys, tmp_path: Path) -> None:
    contrib_dir = tmp_path / "contrib"
    contrib_dir.mkdir()
    _write_tool_file(contrib_dir / "mytools.py", func_name="added_by_codex")

    main(["list-tools", "--contrib-tools-path", str(contrib_dir)])
    out = capsys.readouterr().out.strip()
    tools = json.loads(out)
    assert "added_by_codex" in tools
    assert len(tools) > 1  # base tools also present


def test_list_tools_ignores_private_files(capsys, tmp_path: Path) -> None:
    contrib_dir = tmp_path / "contrib"
    contrib_dir.mkdir()
    _write_tool_file(contrib_dir / "_private.py", func_name="should_not_appear")

    main(["list-tools", "--no-base-tools", "--contrib-tools-path", str(contrib_dir)])
    out = capsys.readouterr().out.strip()
    tools = json.loads(out)
    assert "should_not_appear" not in tools


# ---------------------------------------------------------------------------
# list-plugins
# ---------------------------------------------------------------------------


def test_list_plugins_returns_empty_without_path(capsys) -> None:
    main(["list-plugins"])
    out = capsys.readouterr().out.strip()
    plugins = json.loads(out)
    assert plugins == []


def test_list_plugins_discovers_plugin(capsys, tmp_path: Path) -> None:
    contrib_dir = tmp_path / "contrib"
    contrib_dir.mkdir()
    _write_plugin_file(contrib_dir / "myplugin.py", plugin_name="ai_panel", tab_label="AI")

    main(["list-plugins", "--contrib-tools-path", str(contrib_dir)])
    out = capsys.readouterr().out.strip()
    plugins = json.loads(out)
    assert len(plugins) == 1
    assert plugins[0]["name"] == "ai_panel"
    assert plugins[0]["tab_label"] == "AI"


def test_list_plugins_skips_files_without_elroy_plugin(capsys, tmp_path: Path) -> None:
    contrib_dir = tmp_path / "contrib"
    contrib_dir.mkdir()
    _write_tool_file(contrib_dir / "tools.py")  # tool file, no ELROY_PLUGIN

    main(["list-plugins", "--contrib-tools-path", str(contrib_dir)])
    out = capsys.readouterr().out.strip()
    plugins = json.loads(out)
    assert plugins == []


def test_list_plugins_handles_nonexistent_path(capsys, tmp_path: Path) -> None:
    main(["list-plugins", "--contrib-tools-path", str(tmp_path / "does_not_exist")])
    out = capsys.readouterr().out.strip()
    plugins = json.loads(out)
    assert plugins == []


# ---------------------------------------------------------------------------
# list-codex-sessions
# ---------------------------------------------------------------------------


def test_list_codex_sessions_empty_db(capsys, db_manager) -> None:
    main(["list-codex-sessions", "--database-url", db_manager.url])
    out = capsys.readouterr().out.strip()
    sessions = json.loads(out)
    assert isinstance(sessions, list)


def test_list_codex_sessions_returns_recorded_session(capsys, ctx, db_manager) -> None:
    with open_turn_context(ctx) as turn:
        turn.db.persist(
            CodexSession(
                user_id=turn.user_id,
                thread_id="e2e-cli-test-session",
                repo_path="/tmp/contrib",
                worktree_path=None,
                session_branch=None,
                target_branch=None,
                latest_prompt="add a greeting tool",
                latest_summary="Created greeting tool",
                latest_agent_message="Done.",
                status="completed",
                command_count=1,
                commands_json="[]",
                touched_paths_json='["tools.py"]',
                dirty_paths_before_json="[]",
                dirty_paths_after_json="[]",
                session_file_path=None,
            )
        )

    main(["list-codex-sessions", "--database-url", db_manager.url])
    out = capsys.readouterr().out.strip()
    sessions = json.loads(out)
    assert any(s["session_id"] == "e2e-cli-test-session" for s in sessions)


def test_list_codex_sessions_filters_by_status(capsys, ctx, db_manager) -> None:
    with open_turn_context(ctx) as turn:
        turn.db.persist(
            CodexSession(
                user_id=turn.user_id,
                thread_id="e2e-running-session",
                repo_path="/tmp/contrib",
                worktree_path=None,
                session_branch=None,
                target_branch=None,
                latest_prompt="running task",
                latest_summary="In progress",
                latest_agent_message="",
                status="running",
                command_count=0,
                commands_json="[]",
                touched_paths_json="[]",
                dirty_paths_before_json="[]",
                dirty_paths_after_json="[]",
                session_file_path=None,
            )
        )

    main(["list-codex-sessions", "--database-url", db_manager.url, "--status", "running"])
    out = capsys.readouterr().out.strip()
    sessions = json.loads(out)
    assert all(s["status"] == "running" for s in sessions)
    assert any(s["session_id"] == "e2e-running-session" for s in sessions)


def test_list_codex_sessions_no_running_after_completion(capsys, ctx, db_manager) -> None:
    with open_turn_context(ctx) as turn:
        turn.db.persist(
            CodexSession(
                user_id=turn.user_id,
                thread_id="e2e-completed-session",
                repo_path="/tmp/contrib",
                worktree_path=None,
                session_branch=None,
                target_branch=None,
                latest_prompt="completed task",
                latest_summary="All done",
                latest_agent_message="Finished.",
                status="completed",
                command_count=2,
                commands_json="[]",
                touched_paths_json='["tools.py", "plugin.py"]',
                dirty_paths_before_json="[]",
                dirty_paths_after_json="[]",
                session_file_path=None,
            )
        )

    main(["list-codex-sessions", "--database-url", db_manager.url, "--status", "running"])
    out = capsys.readouterr().out.strip()
    sessions = json.loads(out)
    assert not any(s["session_id"] == "e2e-completed-session" for s in sessions)


# ---------------------------------------------------------------------------
# End-to-end self-improvement flow
# ---------------------------------------------------------------------------


def test_self_improvement_flow(capsys, ctx, db_manager, tmp_path: Path) -> None:
    """Simulate the complete self-improvement cycle:
    1. No contrib tools or plugins initially.
    2. 'Codex' writes new tool + plugin files to contrib.
    3. list-tools shows the new tool.
    4. list-plugins shows the new plugin.
    5. Session recorded as completed is visible via list-codex-sessions.
    """
    contrib_dir = tmp_path / "contrib"
    contrib_dir.mkdir()

    # Step 1: nothing in contrib yet
    main(["list-tools", "--no-base-tools", "--contrib-tools-path", str(contrib_dir)])
    tools_before = json.loads(capsys.readouterr().out.strip())
    assert tools_before == []

    main(["list-plugins", "--contrib-tools-path", str(contrib_dir)])
    plugins_before = json.loads(capsys.readouterr().out.strip())
    assert plugins_before == []

    # Step 2: simulate Codex writing a new tool and plugin
    _write_tool_file(contrib_dir / "generated.py", func_name="self_improvement_tool")
    _write_plugin_file(contrib_dir / "panel.py", plugin_name="self_improvement_panel", tab_label="Self-Improved")

    # Step 3: record the session as completed
    with open_turn_context(ctx) as turn:
        turn.db.persist(
            CodexSession(
                user_id=turn.user_id,
                thread_id="e2e-flow-session",
                repo_path=str(contrib_dir),
                worktree_path=str(contrib_dir),
                session_branch=None,
                target_branch=None,
                latest_prompt="add self improvement tool and panel",
                latest_summary="Created self_improvement_tool and self_improvement_panel",
                latest_agent_message="Done.",
                status="completed",
                command_count=1,
                commands_json="[]",
                touched_paths_json='["generated.py", "panel.py"]',
                dirty_paths_before_json="[]",
                dirty_paths_after_json="[]",
                session_file_path=None,
            )
        )

    # Step 4: new tool is visible
    main(["list-tools", "--no-base-tools", "--contrib-tools-path", str(contrib_dir)])
    tools_after = json.loads(capsys.readouterr().out.strip())
    assert "self_improvement_tool" in tools_after

    # Step 5: new plugin is visible
    main(["list-plugins", "--contrib-tools-path", str(contrib_dir)])
    plugins_after = json.loads(capsys.readouterr().out.strip())
    assert any(p["name"] == "self_improvement_panel" for p in plugins_after)

    # Step 6: no running sessions (session completed)
    main(["list-codex-sessions", "--database-url", db_manager.url, "--status", "running"])
    running = json.loads(capsys.readouterr().out.strip())
    assert not any(s["session_id"] == "e2e-flow-session" for s in running)

    # Step 7: completed session is visible
    main(["list-codex-sessions", "--database-url", db_manager.url, "--status", "completed"])
    completed = json.loads(capsys.readouterr().out.strip())
    assert any(s["session_id"] == "e2e-flow-session" for s in completed)
