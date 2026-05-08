import subprocess
from pathlib import Path

from sqlmodel import select

from elroy.core.session import open_turn_context
from elroy.db.db_models import CodexSession
from elroy.repository.codex_sessions.tools import (
    dispatch_codex_session,
    list_codex_sessions,
    resume_codex_session,
)


def _init_repo(repo_root: Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True, capture_output=True, text=True)
    (repo_root / "notes.txt").write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "notes.txt"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_root, check=True, capture_output=True, text=True)


def test_dispatch_codex_session_persists_summary_and_changes(ctx, monkeypatch, tmp_path: Path):
    development_root = tmp_path / "development"
    repo_root = development_root / "sample"
    _init_repo(repo_root)

    monkeypatch.setattr("elroy.repository.codex_sessions.tools._development_root", lambda: development_root)
    real_run = subprocess.run

    def fake_run(args, *, cwd=None, check=True, capture_output=True, text=True):
        if args[:2] == ["codex", "exec"]:
            (repo_root / "notes.txt").write_text("after\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="\n".join(
                    [
                        '{"type":"thread.started","thread_id":"thread-123"}',
                        '{"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"/bin/zsh -lc pwd","aggregated_output":"'
                        + str(repo_root)
                        + '\\n","exit_code":0,"status":"completed"}}',
                        '{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"updated notes"}}',
                    ]
                ),
                stderr="",
            )
        return real_run(args, cwd=cwd, check=check, capture_output=capture_output, text=text)

    monkeypatch.setattr("elroy.repository.codex_sessions.tools.subprocess.run", fake_run)

    with open_turn_context(ctx) as turn:
        result = dispatch_codex_session("update notes", turn=turn, repo_path="sample")
        records = turn.db.exec(select(CodexSession)).all()

    assert result.session_id == "thread-123"
    assert result.touched_paths == ["notes.txt"]
    assert "updated notes" in result.summary
    assert len(result.commands) == 1
    assert len(records) == 1
    assert records[0].thread_id == "thread-123"
    assert records[0].repo_path == str(repo_root)


def test_resume_and_list_codex_sessions(ctx, monkeypatch, tmp_path: Path):
    development_root = tmp_path / "development"
    repo_root = development_root / "sample"
    _init_repo(repo_root)

    monkeypatch.setattr("elroy.repository.codex_sessions.tools._development_root", lambda: development_root)
    real_run = subprocess.run
    call_count = {"codex": 0}

    def fake_run(args, *, cwd=None, check=True, capture_output=True, text=True):
        if args[:2] == ["codex", "exec"]:
            call_count["codex"] += 1
            if "resume" in args:
                (repo_root / "notes.txt").write_text("after resume\n", encoding="utf-8")
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
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr="")
        return real_run(args, cwd=cwd, check=check, capture_output=capture_output, text=text)

    monkeypatch.setattr("elroy.repository.codex_sessions.tools.subprocess.run", fake_run)

    with open_turn_context(ctx) as turn:
        dispatch_codex_session("first prompt", turn=turn, repo_path="sample")
        resumed = resume_codex_session("thread-123", "follow up", turn=turn)
        listed = list_codex_sessions(turn=turn, repo_path="sample", limit=5)

    assert call_count["codex"] == 2
    assert resumed.final_message == "resume complete"
    assert listed.sessions[0].session_id == "thread-123"
    assert listed.sessions[0].final_message == "resume complete"
    assert listed.sessions[0].repo_path == str(repo_root)
