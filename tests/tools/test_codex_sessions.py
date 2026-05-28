import io
import subprocess
from pathlib import Path

import pytest
from sqlmodel import select

from elroy.core.constants import RecoverableToolError
from elroy.core.session import open_turn_context
from elroy.db.db_models import CodexSession
from elroy.llm.stream_parser import AssistantResponse
from elroy.plugins.registry import PluginRegistry
from elroy.repository.codex_sessions.tools import (
    edit_contrib_with_codex,
    inspect_elroy_with_codex,
    list_codex_sessions,
)

REAL_POPEN = subprocess.Popen


def _init_repo(repo_root: Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True, capture_output=True, text=True)
    (repo_root / "notes.txt").write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "notes.txt"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_root, check=True, capture_output=True, text=True)


class _ImmediateThread:
    def __init__(self, *, target, kwargs=None, daemon=None, name=None):
        self._target = target
        self._kwargs = kwargs or {}
        self.daemon = daemon
        self.name = name

    def start(self) -> None:
        self._target(**self._kwargs)


class _DeferredThread:
    def __init__(self, *, target, kwargs=None, daemon=None, name=None):
        del target, kwargs, daemon, name

    def start(self) -> None:
        return None


class _FakePopen:
    def __init__(self, args, *, cwd=None, stdout_text: str, stderr_text: str = "", returncode: int = 0):
        self.args = args
        self.cwd = cwd
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self.returncode = returncode

    def communicate(self, input=None, timeout=None):
        del input, timeout
        assert self.stdout is not None
        assert self.stderr is not None
        return self.stdout.read(), self.stderr.read()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        del exc_type, exc_val, exc_tb

    def kill(self):
        pass

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        del timeout
        return self.returncode


def test_inspect_elroy_with_codex_runs_directly_against_source_and_logs(ctx, monkeypatch, tmp_path: Path):
    repo_root = tmp_path / "elroy"
    _init_repo(repo_root)
    log_path = tmp_path / "elroy.log"
    log_path.write_text("recent traceback\n", encoding="utf-8")

    monkeypatch.setattr("elroy.repository.codex_sessions.tools._running_elroy_root", lambda: repo_root)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.get_log_file_path", lambda: log_path)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.threading.Thread", _ImmediateThread)

    popen_calls: list[tuple[list[str], str | None]] = []

    def fake_popen(args, **kwargs):
        if args[0] != "codex":
            return REAL_POPEN(args, **kwargs)
        popen_calls.append((args, kwargs.get("cwd")))
        prompt = args[-1]
        assert "Do not edit files" in prompt
        assert str(log_path) in prompt
        assert "recent traceback" in prompt
        stdout = "\n".join(
            [
                '{"type":"thread.started","thread_id":"thread-inspect-001"}',
                '{"type":"item.completed","item":{"id":"i1","type":"agent_message","text":"inspection done"}}',
            ]
        )
        return _FakePopen(args, cwd=kwargs.get("cwd"), stdout_text=stdout)

    def fake_process_message(**kwargs):
        assert kwargs["persist_input_message"] is False
        yield AssistantResponse(content="Inspection complete.")

    monkeypatch.setattr("elroy.repository.codex_sessions.tools.subprocess.Popen", fake_popen)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.process_message", fake_process_message)

    with open_turn_context(ctx) as turn:
        result = inspect_elroy_with_codex("why did startup fail?", turn=turn)

    with open_turn_context(ctx) as turn:
        records = turn.db.exec(select(CodexSession).where(CodexSession.thread_id == "thread-inspect-001")).all()
        listed = list_codex_sessions(turn=turn, scope="elroy", limit=5)

    assert popen_calls == [(popen_calls[0][0], str(repo_root))]
    assert result.session_id == "thread-inspect-001"
    assert result.repo_path == str(repo_root)
    assert result.worktree_path == str(repo_root)
    assert result.session_branch is None
    assert result.target_branch is None

    assert len(records) == 1
    record = records[0]
    assert record.status == "completed"
    assert record.latest_agent_message == "inspection done"
    assert record.touched_paths_json == "[]"
    assert listed.sessions[0].session_id == "thread-inspect-001"


def test_edit_contrib_with_codex_runs_in_home_plugin_repo_and_loaded_by_plugin_system(ctx, monkeypatch, tmp_path: Path):
    home_dir = tmp_path / "elroy-home"

    monkeypatch.setenv("ELROY_HOME", str(home_dir))
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.threading.Thread", _ImmediateThread)

    def fake_popen(args, **kwargs):
        if args[0] != "codex":
            return REAL_POPEN(args, **kwargs)
        worktree_root = Path(kwargs["cwd"])
        (worktree_root / "tools.py").write_text(
            """\
from elroy.core.constants import tool

@tool
def generated_contrib_tool() -> str:
    \"\"\"Return a generated contrib value.

    Returns:
        A generated value.
    \"\"\"
    return "generated"
""",
            encoding="utf-8",
        )
        (worktree_root / "plugin.py").write_text(
            """\
from elroy.plugins.plugin import ElroyPlugin

def _make():
    from textual.widget import Widget
    return Widget()

ELROY_PLUGIN = ElroyPlugin(name="generated_panel", tab_label="Generated", widget_factory=_make)
""",
            encoding="utf-8",
        )
        stdout = "\n".join(
            [
                '{"type":"thread.started","thread_id":"thread-contrib-001"}',
                '{"type":"item.completed","item":{"id":"i1","type":"agent_message","text":"contrib improvement done"}}',
            ]
        )
        return _FakePopen(args, cwd=kwargs.get("cwd"), stdout_text=stdout)

    def fake_process_message(**kwargs):
        assert kwargs["persist_input_message"] is False
        yield AssistantResponse(content="Contrib improvement complete.")

    monkeypatch.setattr("elroy.repository.codex_sessions.tools.subprocess.Popen", fake_popen)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.process_message", fake_process_message)

    with open_turn_context(ctx) as turn:
        result = edit_contrib_with_codex("add generated contrib tool and panel", turn=turn)

    contrib_repo = home_dir / "contrib"
    current_branch = subprocess.run(
        ["git", "-C", str(contrib_repo), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(contrib_repo), "status", "--porcelain=v1"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    with open_turn_context(ctx) as turn:
        records = turn.db.exec(select(CodexSession).where(CodexSession.thread_id == "thread-contrib-001")).all()
        listed = list_codex_sessions(turn=turn, scope="contrib", limit=5)

    assert result.session_id == "thread-contrib-001"
    assert result.repo_path == str(contrib_repo)
    assert result.worktree_path == str(contrib_repo)
    assert result.session_branch is None
    assert result.target_branch is None
    assert current_branch == "agent"
    assert status == ""

    assert len(records) == 1
    record = records[0]
    assert record.repo_path == str(contrib_repo)
    assert record.status == "completed"
    assert record.latest_agent_message == "contrib improvement done"
    assert listed.sessions[0].session_id == "thread-contrib-001"

    reloaded_ctx = ctx.__class__(
        database_url=ctx.database_url,
        chroma_path=ctx.chroma_path,
        model_config=ctx.model_config,
        ui_config=ctx.ui_config,
        memory_config=ctx.memory_config,
        runtime_config=ctx.runtime_config,
        include_base_tools=False,
        contrib_tools_path=str(contrib_repo),
    )
    assert "generated_contrib_tool" in reloaded_ctx.tool_registry
    generated_tool = reloaded_ctx.tool_registry.get("generated_contrib_tool")
    assert generated_tool is not None
    assert generated_tool() == "generated"

    registry = PluginRegistry.from_path(str(contrib_repo))
    assert [plugin.name for plugin in registry.plugins] == ["generated_panel"]


def test_edit_contrib_with_codex_returns_running_result_before_background_completion(ctx, monkeypatch, tmp_path: Path):
    home_dir = tmp_path / "elroy-home"
    monkeypatch.setenv("ELROY_HOME", str(home_dir))
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.threading.Thread", _DeferredThread)

    def fake_popen(args, **kwargs):
        if args[0] != "codex":
            return REAL_POPEN(args, **kwargs)
        stdout = '{"type":"thread.started","thread_id":"thread-running-001"}\n'
        return _FakePopen(args, cwd=kwargs.get("cwd"), stdout_text=stdout)

    monkeypatch.setattr("elroy.repository.codex_sessions.tools.subprocess.Popen", fake_popen)

    with open_turn_context(ctx) as turn:
        result = edit_contrib_with_codex("slow edit", turn=turn)

    assert result.status == "running"
    assert result.running_in_background is True
    assert result.repo_path == str(home_dir / "contrib")
    assert result.session_branch is None
    assert result.target_branch is None


def test_list_codex_sessions_rejects_unknown_scope(ctx):
    with open_turn_context(ctx) as turn, pytest.raises(RecoverableToolError, match="scope must be"):
        list_codex_sessions(turn=turn, scope="other")
