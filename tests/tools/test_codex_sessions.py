import io
import subprocess
from pathlib import Path

import pytest
from sqlmodel import select

from elroy.core.constants import RecoverableToolError
from elroy.core.session import open_turn_context
from elroy.db.db_models import CodexSession
from elroy.llm.stream_parser import AssistantResponse
from elroy.repository.codex_sessions import tools as codex_tools
from elroy.repository.codex_sessions.tools import (
    dispatch_codex_session,
    list_codex_sessions,
    resume_codex_session,
)

REAL_POPEN = subprocess.Popen


def _write_fake_elroy_source_tree(source_root: Path) -> Path:
    module_file = source_root / "elroy" / "repository" / "codex_sessions" / "tools.py"
    module_file.parent.mkdir(parents=True, exist_ok=True)
    module_file.write_text("", encoding="utf-8")
    (source_root / "pyproject.toml").write_text("[project]\nname = 'elroy'\n", encoding="utf-8")
    return module_file


def _init_repo(repo_root: Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True, capture_output=True, text=True)
    (repo_root / "notes.txt").write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "notes.txt"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_root, check=True, capture_output=True, text=True)


def test_resolve_repo_path_uses_running_elroy_checkout_parent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home_development_repo = home / "development" / "sample"
    _init_repo(home_development_repo)

    workspace_root = tmp_path / "Workspaces"
    repo_root = workspace_root / "sample"
    _init_repo(repo_root)
    module_file = _write_fake_elroy_source_tree(workspace_root / "elroy")

    cwd = tmp_path / "outside-workspace"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(codex_tools, "__file__", str(module_file))

    assert codex_tools._development_root() == workspace_root.resolve()
    assert codex_tools._resolve_repo_path("sample") == repo_root.resolve()


class _ImmediateThread:
    def __init__(self, *, target, kwargs=None, daemon=None, name=None):
        self._target = target
        self._kwargs = kwargs or {}
        self.daemon = daemon
        self.name = name

    def start(self) -> None:
        self._target(**self._kwargs)


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
        pass

    def kill(self):
        pass

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        del timeout
        return self.returncode


def test_dispatch_codex_session_runs_in_background_and_persists_completion(ctx, monkeypatch, tmp_path: Path):
    development_root = tmp_path / "development"
    repo_root = development_root / "sample"
    _init_repo(repo_root)
    subprocess.run(["git", "-C", str(repo_root), "branch", "agent", "HEAD"], check=True, capture_output=True)

    monkeypatch.setattr("elroy.repository.codex_sessions.tools._development_root", lambda: development_root)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.threading.Thread", _ImmediateThread)

    def fake_popen(args, **kwargs):
        if args[0] != "codex":
            return REAL_POPEN(args, **kwargs)
        worktree_root = Path(kwargs["cwd"])
        (worktree_root / "notes.txt").write_text("after\n", encoding="utf-8")
        stdout = "\n".join(
            [
                '{"type":"thread.started","thread_id":"thread-123"}',
                '{"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"/bin/zsh -lc pwd","aggregated_output":"'
                + str(worktree_root)
                + '\\n","exit_code":0,"status":"completed"}}',
                '{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"updated notes"}}',
            ]
        )
        return _FakePopen(args, cwd=kwargs.get("cwd"), stdout_text=stdout)

    def fake_process_message(**kwargs):
        assert kwargs["persist_input_message"] is False
        yield AssistantResponse(content="Background review complete.")

    monkeypatch.setattr("elroy.repository.codex_sessions.tools.subprocess.Popen", fake_popen)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.process_message", fake_process_message)

    with open_turn_context(ctx) as turn:
        result = dispatch_codex_session("update notes", turn=turn, repo_path="sample")

    with open_turn_context(ctx) as turn:
        records = turn.db.exec(select(CodexSession)).all()

    assert result.session_id == "thread-123"
    assert result.status == "running"
    assert result.running_in_background is True
    assert result.worktree_path is not None
    assert result.session_branch is not None
    assert result.target_branch == "agent"
    assert len(records) == 1
    assert records[0].thread_id == "thread-123"
    assert records[0].repo_path == str(repo_root)
    assert records[0].status == "completed"
    assert records[0].latest_agent_message == "updated notes"
    assert records[0].worktree_path is not None
    assert "Removed session worktree" in (records[0].latest_summary or "")
    assert "Removed session branch" in (records[0].latest_summary or "")
    assert not Path(records[0].worktree_path).exists()
    assert records[0].session_branch is not None
    assert records[0].target_branch == "agent"
    agent_head = subprocess.run(
        ["git", "-C", str(repo_root), "show", "agent:notes.txt"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert agent_head == "after\n"


def test_resume_and_list_codex_sessions_runs_async(ctx, monkeypatch, tmp_path: Path):
    development_root = tmp_path / "development"
    repo_root = development_root / "sample"
    _init_repo(repo_root)
    subprocess.run(["git", "-C", str(repo_root), "branch", "agent", "HEAD"], check=True, capture_output=True)

    monkeypatch.setattr("elroy.repository.codex_sessions.tools._development_root", lambda: development_root)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.threading.Thread", _ImmediateThread)
    popen_calls: list[tuple[list[str], str | None]] = []

    def fake_popen(args, **kwargs):
        if args[0] != "codex":
            return REAL_POPEN(args, **kwargs)
        popen_calls.append((args, kwargs.get("cwd")))
        worktree_root = Path(kwargs["cwd"])
        if "resume" in args:
            (worktree_root / "notes.txt").write_text("after resume\n", encoding="utf-8")
            stdout = "\n".join(
                [
                    '{"type":"thread.started","thread_id":"thread-123"}',
                    '{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"resume complete"}}',
                ]
            )
        else:
            stdout = "\n".join(
                [
                    '{"type":"thread.started","thread_id":"thread-123"}',
                    '{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"initial complete"}}',
                ]
            )
        return _FakePopen(args, cwd=kwargs.get("cwd"), stdout_text=stdout)

    def fake_process_message(**kwargs):
        assert kwargs["persist_input_message"] is False
        yield AssistantResponse(content="Background review complete.")

    monkeypatch.setattr("elroy.repository.codex_sessions.tools.subprocess.Popen", fake_popen)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.process_message", fake_process_message)

    with open_turn_context(ctx) as turn:
        initial = dispatch_codex_session("first prompt", turn=turn, repo_path="sample")

    with open_turn_context(ctx) as turn:
        resumed = resume_codex_session("thread-123", "follow up", turn=turn)
        listed = list_codex_sessions(turn=turn, repo_path="sample", limit=5)

    assert initial.status == "running"
    assert resumed.status == "running"
    assert len(popen_calls) == 2
    assert popen_calls[1][1] != str(repo_root)
    assert listed.sessions[0].session_id == "thread-123"
    assert listed.sessions[0].final_message == "resume complete"
    assert listed.sessions[0].repo_path == str(repo_root)
    assert listed.sessions[0].status == "completed"
    assert "Removed session worktree" in listed.sessions[0].summary
    assert "Removed session branch" in listed.sessions[0].summary
    agent_head = subprocess.run(
        ["git", "-C", str(repo_root), "show", "agent:notes.txt"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert agent_head == "after resume\n"


def test_resume_running_session_is_rejected(ctx, monkeypatch, tmp_path: Path):
    development_root = tmp_path / "development"
    repo_root = development_root / "sample"
    _init_repo(repo_root)
    subprocess.run(["git", "-C", str(repo_root), "branch", "agent", "HEAD"], check=True, capture_output=True)

    monkeypatch.setattr("elroy.repository.codex_sessions.tools._development_root", lambda: development_root)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.threading.Thread", _ImmediateThread)

    def fake_popen(args, **kwargs):
        if args[0] != "codex":
            return REAL_POPEN(args, **kwargs)
        stdout = '{"type":"thread.started","thread_id":"thread-123"}\n'
        return _FakePopen(args, stdout_text=stdout, returncode=0)

    def fake_store_background(*args, **kwargs):
        del args, kwargs
        return

    monkeypatch.setattr("elroy.repository.codex_sessions.tools.subprocess.Popen", fake_popen)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools._complete_codex_session_in_background", fake_store_background)

    with open_turn_context(ctx) as turn:
        dispatch_codex_session("first prompt", turn=turn, repo_path="sample")
        with pytest.raises(RecoverableToolError, match="still running"):
            resume_codex_session("thread-123", "follow up", turn=turn)


def test_dispatch_allows_multiple_isolated_sessions_for_same_repo(ctx, monkeypatch, tmp_path: Path):
    development_root = tmp_path / "development"
    repo_root = development_root / "sample"
    _init_repo(repo_root)
    subprocess.run(["git", "-C", str(repo_root), "branch", "agent", "HEAD"], check=True, capture_output=True)

    monkeypatch.setattr("elroy.repository.codex_sessions.tools._development_root", lambda: development_root)

    class _DeferredThread:
        def __init__(self, *, target, kwargs=None, daemon=None, name=None):
            del target, kwargs, daemon, name

        def start(self) -> None:
            return None

    session_counter = 0
    codex_cwds: list[str] = []

    def fake_popen(args, **kwargs):
        nonlocal session_counter
        if args[0] != "codex":
            return REAL_POPEN(args, **kwargs)
        session_counter += 1
        codex_cwds.append(str(kwargs["cwd"]))
        stdout = f'{{"type":"thread.started","thread_id":"thread-{session_counter}"}}\n'
        return _FakePopen(args, cwd=kwargs.get("cwd"), stdout_text=stdout, returncode=0)

    monkeypatch.setattr("elroy.repository.codex_sessions.tools.threading.Thread", _DeferredThread)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.subprocess.Popen", fake_popen)

    with open_turn_context(ctx) as turn:
        first = dispatch_codex_session("first prompt", turn=turn, repo_path="sample")
        second = dispatch_codex_session("second prompt", turn=turn, repo_path="sample")
        listed = list_codex_sessions(turn=turn, repo_path="sample", limit=10)

    assert first.status == "running"
    assert second.status == "running"
    assert first.session_id != second.session_id
    assert first.worktree_path
    assert second.worktree_path
    assert first.worktree_path != second.worktree_path
    assert first.session_branch
    assert second.session_branch
    assert first.session_branch != second.session_branch
    assert codex_cwds == [first.worktree_path, second.worktree_path]

    assert len(listed.sessions) == 2
    listed_by_id = {session.session_id: session for session in listed.sessions}
    assert listed_by_id["thread-1"].worktree_path == first.worktree_path
    assert listed_by_id["thread-1"].session_branch == first.session_branch
    assert listed_by_id["thread-1"].target_branch == "agent"
    assert listed_by_id["thread-1"].status == "running"
    assert listed_by_id["thread-2"].worktree_path == second.worktree_path
    assert listed_by_id["thread-2"].session_branch == second.session_branch
    assert listed_by_id["thread-2"].target_branch == "agent"
    assert listed_by_id["thread-2"].status == "running"


def test_dev_root_boundary_enforced(ctx, monkeypatch, tmp_path: Path):
    """Repos outside the development root are rejected; any repo inside it is allowed."""
    development_root = tmp_path / "development"
    inside_repo = development_root / "my-project"
    outside_repo = tmp_path / "outside" / "project"
    _init_repo(inside_repo)
    _init_repo(outside_repo)

    monkeypatch.setattr("elroy.repository.codex_sessions.tools._development_root", lambda: development_root)

    with open_turn_context(ctx) as turn:
        # Outside the dev root — rejected
        with pytest.raises(RecoverableToolError, match="outside the development root"):
            dispatch_codex_session("prompt", turn=turn, repo_path=str(outside_repo))

        # Inside the dev root — proceeds past boundary check (Codex not launched, so fails later)
        def fake_popen(args, **kwargs):
            if args[0] != "codex":
                return REAL_POPEN(args, **kwargs)
            stdout = '{"type":"thread.started","thread_id":"thread-boundary-1"}\n'
            return _FakePopen(args, stdout_text=stdout, returncode=0)

        class _DeferredThread:
            def __init__(self, *, target, kwargs=None, daemon=None, name=None):
                del target, kwargs, daemon, name

            def start(self) -> None:
                return None

        monkeypatch.setattr("elroy.repository.codex_sessions.tools.subprocess.Popen", fake_popen)
        monkeypatch.setattr("elroy.repository.codex_sessions.tools.threading.Thread", _DeferredThread)

        result = dispatch_codex_session("prompt", turn=turn, repo_path=str(inside_repo))
        assert result.status == "running"


def test_e2e_self_improvement_dispatch_from_main_branch(ctx, monkeypatch, tmp_path: Path):
    """
    End-to-end test for the self-improvement flow running from the main branch.

    Verifies that dispatch works without being on the agent branch — the agent
    branch is created automatically, Codex runs in an isolated session worktree,
    and its changes are merged into the agent branch.
    """
    development_root = tmp_path / "development"
    repo_root = development_root / "elroy"
    _init_repo(repo_root)
    # agent branch does NOT exist yet — should be auto-created

    monkeypatch.setattr("elroy.repository.codex_sessions.tools._development_root", lambda: development_root)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.threading.Thread", _ImmediateThread)

    def fake_popen(args, **kwargs):
        if args[0] != "codex":
            return REAL_POPEN(args, **kwargs)
        worktree_root = Path(kwargs["cwd"])
        (worktree_root / "improvement.txt").write_text("improved\n", encoding="utf-8")
        stdout = "\n".join(
            [
                '{"type":"thread.started","thread_id":"thread-e2e-001"}',
                '{"type":"item.completed","item":{"id":"i1","type":"agent_message","text":"self-improvement done"}}',
            ]
        )
        return _FakePopen(args, cwd=kwargs.get("cwd"), stdout_text=stdout)

    def fake_process_message(**kwargs):
        assert kwargs["persist_input_message"] is False
        yield AssistantResponse(content="Improvement complete.")

    monkeypatch.setattr("elroy.repository.codex_sessions.tools.subprocess.Popen", fake_popen)
    monkeypatch.setattr("elroy.repository.codex_sessions.tools.process_message", fake_process_message)

    with open_turn_context(ctx) as turn:
        result = dispatch_codex_session("add improvement.txt", turn=turn, repo_path="elroy")

    with open_turn_context(ctx) as turn:
        records = turn.db.exec(select(CodexSession).where(CodexSession.thread_id == "thread-e2e-001")).all()

    assert result.session_id == "thread-e2e-001"
    assert result.status == "running"
    assert result.target_branch == "agent"

    assert len(records) == 1
    record = records[0]
    assert record.status == "completed"
    assert record.latest_agent_message == "self-improvement done"
    assert "Removed session worktree" in (record.latest_summary or "")
    assert "Removed session branch" in (record.latest_summary or "")

    # The improvement should be on the agent branch in the repo
    agent_file = subprocess.run(
        ["git", "-C", str(repo_root), "show", "agent:improvement.txt"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert agent_file == "improved\n"
