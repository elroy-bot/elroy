import hashlib
import json
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ...config.paths import get_log_file_path
from ...core.constants import RecoverableToolError, tool
from ...core.session import clone_config, invoke_with_config
from ...core.turn import TurnContext
from ...messenger.messenger import process_message
from ...repository.contrib.tools import ensure_contrib_repo
from .store import CodexSessionStore, CodexSessionUpdate

CODEX_SESSION_SEARCH_ROOT = Path.home() / ".codex" / "sessions"
DEFAULT_CODEX_SESSION_LIMIT = 5
MAX_COMMAND_OUTPUT_CHARS = 400
MAX_LOG_EXCERPT_CHARS = 6000


class CodexCommandSummary(BaseModel):
    command: str
    exit_code: int | None = None
    output_excerpt: str = ""


class CodexSessionResult(BaseModel):
    session_id: str
    repo_path: str
    worktree_path: str | None = None
    session_branch: str | None = None
    target_branch: str | None = None
    status: str
    final_message: str
    summary: str
    touched_paths: list[str]
    dirty_paths_before: list[str]
    dirty_paths_after: list[str]
    commands: list[CodexCommandSummary]
    session_file_path: str | None = None
    resume_command: str
    running_in_background: bool = False


class CodexSessionListEntry(BaseModel):
    session_id: str
    repo_path: str
    worktree_path: str | None = None
    session_branch: str | None = None
    target_branch: str | None = None
    status: str
    updated_at: str
    summary: str | None = None
    final_message: str | None = None
    touched_paths: list[str]


class CodexSessionListResult(BaseModel):
    sessions: list[CodexSessionListEntry]


class RepoSnapshot(BaseModel):
    status_by_path: dict[str, str]
    fingerprint_by_path: dict[str, str]


@dataclass(frozen=True)
class CodexRunContext:
    source_repo_root: Path
    worktree_root: Path
    before: RepoSnapshot


@dataclass(frozen=True)
class CodexBackgroundRun:
    config: Any
    prompt: str
    context: CodexRunContext
    process: subprocess.Popen[str]
    initial_stdout: str
    commit_changes: bool


def _run_subprocess(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=check,
    )


def _running_elroy_root() -> Path | None:
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "elroy").is_dir():
            return parent
    return None


def _parse_status_lines(output: str) -> dict[str, str]:
    status_by_path: dict[str, str] = {}
    for line in output.splitlines():
        if len(line) < 4:
            continue
        status = line[:2]
        path_text = line[3:]
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        status_by_path[path_text] = status
    return status_by_path


def _hash_path(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_fingerprint(repo_root: Path, rel_path: str, status: str) -> str:
    path = repo_root / rel_path
    if status == "??" and path.exists() and path.is_file():
        return _hash_path(path)

    result = _run_subprocess(
        ["git", "-C", str(repo_root), "diff", "--no-ext-diff", "--no-color", "HEAD", "--", rel_path],
        check=False,
    )
    if result.returncode not in {0, 1}:
        return f"missing:{status}"
    return hashlib.sha1(result.stdout.encode("utf-8")).hexdigest()


def _snapshot_repo(repo_root: Path) -> RepoSnapshot:
    status_output = _run_subprocess(["git", "-C", str(repo_root), "status", "--porcelain=v1", "-uall"]).stdout
    status_by_path = _parse_status_lines(status_output)
    fingerprint_by_path = {rel_path: _path_fingerprint(repo_root, rel_path, status) for rel_path, status in status_by_path.items()}
    return RepoSnapshot(status_by_path=status_by_path, fingerprint_by_path=fingerprint_by_path)


def _touched_paths(before: RepoSnapshot, after: RepoSnapshot) -> list[str]:
    touched = []
    for rel_path in sorted(set(before.status_by_path) | set(after.status_by_path)):
        if before.status_by_path.get(rel_path) != after.status_by_path.get(rel_path):
            touched.append(rel_path)
            continue
        if before.fingerprint_by_path.get(rel_path) != after.fingerprint_by_path.get(rel_path):
            touched.append(rel_path)
    return touched


def _session_file_path(thread_id: str) -> str | None:
    if not CODEX_SESSION_SEARCH_ROOT.exists():
        return None
    match = next(CODEX_SESSION_SEARCH_ROOT.rglob(f"*{thread_id}.jsonl"), None)
    return str(match) if match else None


def _parse_codex_exec_output(stdout: str) -> tuple[str, str, list[CodexCommandSummary]]:
    thread_id = ""
    final_message = ""
    commands: list[CodexCommandSummary] = []

    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        payload = json.loads(line)
        event_type = payload.get("type")
        if event_type == "thread.started":
            thread_id = str(payload.get("thread_id") or "")
            continue
        if event_type != "item.completed":
            continue
        item = payload.get("item", {})
        item_type = item.get("type")
        if item_type == "agent_message":
            final_message = str(item.get("text") or final_message)
        elif item_type == "command_execution":
            commands.append(
                CodexCommandSummary(
                    command=str(item.get("command") or ""),
                    exit_code=item.get("exit_code"),
                    output_excerpt=str(item.get("aggregated_output") or "")[:MAX_COMMAND_OUTPUT_CHARS],
                )
            )

    if not thread_id:
        raise RecoverableToolError("Codex did not emit a thread id.")
    if not final_message:
        raise RecoverableToolError("Codex did not emit a final assistant message.")
    return thread_id, final_message, commands


def _parse_thread_started(stdout: str) -> str | None:
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        payload = json.loads(line)
        if payload.get("type") == "thread.started":
            thread_id = str(payload.get("thread_id") or "")
            return thread_id or None
    return None


def _build_codex_args(prompt: str, repo_root: Path, *, model: str | None = None) -> list[str]:
    args = ["codex", "exec", "--json", "--dangerously-bypass-approvals-and-sandbox", "-C", str(repo_root), prompt]
    if model:
        args[3:3] = ["-m", model]
    return args


def _build_summary(
    session_id: str,
    context: CodexRunContext,
    touched_paths: list[str],
    dirty_before: list[str],
    dirty_after: list[str],
    final_message: str,
    note: str | None = None,
) -> str:
    lines = [f"Codex session {session_id} ran directly in {context.worktree_root} for source repo {context.source_repo_root}."]
    if touched_paths:
        lines.append("Paths changed during this run: " + ", ".join(touched_paths[:10]))
    else:
        lines.append("No repository changes were detected during this run.")
    if dirty_before:
        lines.append("Repo was already dirty before run: " + ", ".join(dirty_before[:10]))
    if dirty_after:
        lines.append("Dirty paths after run: " + ", ".join(dirty_after[:10]))
    if note:
        lines.append(note)
    lines.append("Final message: " + final_message.strip())
    return "\n".join(lines)


def _build_running_result(
    session_id: str,
    source_repo_root: Path,
    worktree_root: Path,
    before: RepoSnapshot,
    purpose: str,
) -> CodexSessionResult:
    dirty_before = sorted(before.status_by_path)
    return CodexSessionResult(
        session_id=session_id,
        repo_path=str(source_repo_root),
        worktree_path=str(worktree_root),
        session_branch=None,
        target_branch=None,
        status="running",
        final_message="",
        summary=f"Codex {purpose} session {session_id} is running asynchronously in {worktree_root}.",
        touched_paths=[],
        dirty_paths_before=dirty_before,
        dirty_paths_after=dirty_before,
        commands=[],
        session_file_path=None,
        resume_command=f"codex resume {session_id} -C {worktree_root}",
        running_in_background=True,
    )


def _build_failed_result(
    session_id: str, source_repo_root: Path, worktree_root: Path, before: RepoSnapshot, stderr: str
) -> CodexSessionResult:
    dirty_before = sorted(before.status_by_path)
    message = stderr.strip() or "Codex run failed."
    return CodexSessionResult(
        session_id=session_id,
        repo_path=str(source_repo_root),
        worktree_path=str(worktree_root),
        session_branch=None,
        target_branch=None,
        status="failed",
        final_message=message,
        summary=f"Codex session {session_id} failed in {worktree_root}: {message}",
        touched_paths=[],
        dirty_paths_before=dirty_before,
        dirty_paths_after=dirty_before,
        commands=[],
        session_file_path=None,
        resume_command=f"codex resume {session_id} -C {worktree_root}",
    )


def _build_result_from_stdout(
    stdout: str,
    context: CodexRunContext,
    note: str | None = None,
) -> CodexSessionResult:
    resolved_session_id, final_message, commands = _parse_codex_exec_output(stdout)
    after = _snapshot_repo(context.worktree_root)
    touched_paths = _touched_paths(context.before, after)
    dirty_before = sorted(context.before.status_by_path)
    dirty_after = sorted(after.status_by_path)
    summary = _build_summary(
        resolved_session_id,
        context,
        touched_paths,
        dirty_before,
        dirty_after,
        final_message,
        note=note,
    )
    return CodexSessionResult(
        session_id=resolved_session_id,
        repo_path=str(context.source_repo_root),
        worktree_path=str(context.worktree_root),
        session_branch=None,
        target_branch=None,
        status="completed",
        final_message=final_message,
        summary=summary,
        touched_paths=touched_paths,
        dirty_paths_before=dirty_before,
        dirty_paths_after=dirty_after,
        commands=commands,
        session_file_path=_session_file_path(resolved_session_id),
        resume_command=f"codex resume {resolved_session_id} -C {context.worktree_root}",
    )


def _worktree_has_uncommitted_changes(worktree_root: Path) -> bool:
    result = _run_subprocess(["git", "-C", str(worktree_root), "status", "--porcelain=v1", "-uall"], check=False)
    return bool(result.stdout.strip())


def _commit_worktree_if_needed(worktree_root: Path, session_id: str) -> str | None:
    if not _worktree_has_uncommitted_changes(worktree_root):
        return None
    _run_subprocess(["git", "-C", str(worktree_root), "add", "-A"])
    _run_subprocess(["git", "-C", str(worktree_root), "commit", "-m", f"Elroy Codex contrib update ({session_id})"])
    return f"Committed contrib changes for Codex session {session_id}."


def _store_result(turn: TurnContext, prompt: str, result: CodexSessionResult) -> None:
    CodexSessionStore(turn.db, turn.user_id).upsert(
        result.session_id,
        CodexSessionUpdate(
            repo_path=Path(result.repo_path),
            worktree_path=Path(result.worktree_path) if result.worktree_path else None,
            session_branch=result.session_branch,
            target_branch=result.target_branch,
            prompt=prompt,
            summary=result.summary,
            agent_message=result.final_message,
            status=result.status,
            commands=[command.model_dump() for command in result.commands],
            touched_paths=result.touched_paths,
            dirty_paths_before=result.dirty_paths_before,
            dirty_paths_after=result.dirty_paths_after,
            session_file_path=result.session_file_path,
        ),
    )


def _completion_followup_prompt(result: CodexSessionResult) -> str:
    return (
        f"A background Codex session completed.\n\n"
        f"Session: {result.session_id}\n"
        f"Repository: {result.repo_path}\n"
        f"Worktree: {result.worktree_path or 'n/a'}\n"
        f"Status: {result.status}\n"
        f"Summary:\n{result.summary}\n\n"
        "Respond to the user about the outcome and decide whether any follow-up action is needed."
    )


def _persist_background_codex_result(prompt: str, result_json: str, turn: TurnContext) -> None:
    result = CodexSessionResult.model_validate_json(result_json)
    _store_result(turn, prompt, result)
    list(
        process_message(
            role="user",
            ctx=turn.config,
            session=turn.session,
            msg=_completion_followup_prompt(result),
            persist_input_message=False,
        )
    )


def _complete_codex_session_in_background(run: CodexBackgroundRun) -> None:
    stdout_tail, stderr_text = run.process.communicate()
    stdout = run.initial_stdout + (stdout_tail or "")
    context = run.context

    try:
        if run.process.returncode not in {0, None}:
            session_id = _parse_thread_started(stdout) or "unknown"
            result = _build_failed_result(
                session_id,
                context.source_repo_root,
                context.worktree_root,
                context.before,
                stderr_text or stdout,
            )
        else:
            result = _build_result_from_stdout(stdout, context)
            if run.commit_changes:
                commit_note = _commit_worktree_if_needed(context.worktree_root, result.session_id)
                if commit_note:
                    clean_after_commit = _snapshot_repo(context.worktree_root)
                    result.dirty_paths_after = sorted(clean_after_commit.status_by_path)
                    result.summary = "\n".join([result.summary, commit_note])
    except Exception as exc:
        session_id = _parse_thread_started(stdout) or "unknown"
        result = _build_failed_result(session_id, context.source_repo_root, context.worktree_root, context.before, str(exc))

    new_ctx = clone_config(run.config)
    invoke_with_config(_persist_background_codex_result, new_ctx, run.prompt, result.model_dump_json())


def _prepare_codex_async_run(
    prompt: str,
    source_repo_root: Path,
    worktree_root: Path,
    turn: TurnContext,
    *,
    purpose: str,
    commit_changes: bool,
    model: str | None = None,
) -> tuple[CodexSessionResult, threading.Thread]:
    before = _snapshot_repo(worktree_root)
    context = CodexRunContext(source_repo_root=source_repo_root, worktree_root=worktree_root, before=before)
    args = _build_codex_args(prompt, worktree_root, model=model)

    try:
        process = subprocess.Popen(
            args,
            cwd=str(worktree_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
    except Exception as exc:
        raise RecoverableToolError(f"Unable to launch Codex asynchronously: {exc}") from exc

    assert process.stdout is not None
    initial_stdout_lines: list[str] = []
    resolved_session_id: str | None = None

    while True:
        line = process.stdout.readline()
        if line == "":
            _, stderr_text = process.communicate()
            stderr = (stderr_text or "").strip() or "".join(initial_stdout_lines).strip() or "Codex exited before emitting a thread id."
            raise RecoverableToolError(f"Codex run failed: {stderr}")
        initial_stdout_lines.append(line)
        resolved_session_id = _parse_thread_started("".join(initial_stdout_lines))
        if resolved_session_id:
            break

    running_result = _build_running_result(resolved_session_id, source_repo_root, worktree_root, before, purpose)
    background_thread = threading.Thread(
        target=_complete_codex_session_in_background,
        kwargs={
            "run": CodexBackgroundRun(
                config=turn.config,
                prompt=prompt,
                context=context,
                process=process,
                initial_stdout="".join(initial_stdout_lines),
                commit_changes=commit_changes,
            ),
        },
        daemon=True,
        name=f"codex-session-{resolved_session_id}",
    )
    return running_result, background_thread


def _tail_log_excerpt(max_chars: int = MAX_LOG_EXCERPT_CHARS) -> str:
    log_path = get_log_file_path()
    if not log_path.exists():
        return ""
    try:
        return log_path.read_text(encoding="utf-8")[-max_chars:]
    except UnicodeDecodeError:
        return ""


def _build_inspection_prompt(prompt: str, include_logs: bool) -> str:
    log_path = get_log_file_path()
    log_excerpt = _tail_log_excerpt() if include_logs else ""
    log_section = f"\n\nElroy log path: {log_path}\nRecent log excerpt:\n{log_excerpt}" if include_logs else ""
    return (
        "Inspect the running Elroy codebase and logs. Do not edit files. Report concrete findings, risks, and suggested next steps.\n\n"
        f"Inspection request:\n{prompt}"
        f"{log_section}"
    )


def _build_contrib_edit_prompt(prompt: str, contrib_repo: Path) -> str:
    return (
        "Edit only the Elroy contrib plugin directory for this task. Do not modify core Elroy source code. "
        "Contrib Python files may define @tool functions and/or ELROY_PLUGIN = ElroyPlugin(...) sidebar plugins. "
        "Keep changes small and directly related to the request.\n\n"
        f"Contrib directory: {contrib_repo}\n\n"
        f"Edit request:\n{prompt}"
    )


def _repo_filter_for_scope(scope: str | None) -> Path | None:
    if scope is None:
        return None
    if scope == "contrib":
        return ensure_contrib_repo()
    if scope == "elroy":
        return _running_elroy_root() or Path.cwd().resolve()
    raise RecoverableToolError("scope must be 'contrib', 'elroy', or omitted")


@tool
def inspect_elroy_with_codex(prompt: str, turn: TurnContext, include_logs: bool = True, model: str | None = None) -> CodexSessionResult:
    """Run a read-only Codex inspection session against the running Elroy source tree and optional logs.

    Use this when you want a separate Codex session to investigate bugs, inspect code paths, or review
    recent logs without making edits.

    Args:
        prompt: Inspection question or task for Codex.
        turn: Active turn context for persistence.
        include_logs: Whether to include the Elroy log path and recent log excerpt in the Codex prompt.
        model: Optional Codex model override.
    """
    source_repo_root = _running_elroy_root() or Path.cwd().resolve()
    result, background_thread = _prepare_codex_async_run(
        _build_inspection_prompt(prompt, include_logs),
        source_repo_root,
        source_repo_root,
        turn,
        purpose="inspection",
        commit_changes=False,
        model=model,
    )
    _store_result(turn, prompt, result)
    background_thread.start()
    return result


@tool
def edit_contrib_with_codex(prompt: str, turn: TurnContext, model: str | None = None) -> CodexSessionResult:
    """Run a Codex edit session directly in the Elroy-home contrib plugin directory.

    Use this for assistant self-improvements that should be loaded through the plugin system instead
    of changing core Elroy source code. Elroy ensures the contrib directory exists as a git repo,
    runs Codex directly in that directory, records the session, and commits completed changes.

    Args:
        prompt: Plugin/tool edit request for Codex.
        turn: Active turn context for persistence.
        model: Optional Codex model override.
    """
    contrib_repo = ensure_contrib_repo()
    result, background_thread = _prepare_codex_async_run(
        _build_contrib_edit_prompt(prompt, contrib_repo),
        contrib_repo,
        contrib_repo,
        turn,
        purpose="contrib edit",
        commit_changes=True,
        model=model,
    )
    _store_result(turn, prompt, result)
    background_thread.start()
    return result


@tool
def list_codex_sessions(turn: TurnContext, scope: str | None = None, limit: int = DEFAULT_CODEX_SESSION_LIMIT) -> CodexSessionListResult:
    """List recently recorded Codex sessions and their latest summaries.

    Args:
        turn: Active turn context for persistence.
        scope: Optional filter. Use "contrib" for plugin-directory sessions or "elroy" for running-code inspection sessions.
        limit: Maximum number of sessions to return.
    """
    if limit < 1:
        raise RecoverableToolError("limit must be at least 1")

    repo_root = _repo_filter_for_scope(scope)
    records = CodexSessionStore(turn.db, turn.user_id).list_recent(repo_path=repo_root, limit=limit)
    return CodexSessionListResult(
        sessions=[
            CodexSessionListEntry(
                session_id=record.thread_id,
                repo_path=record.repo_path,
                worktree_path=record.worktree_path,
                session_branch=record.session_branch,
                target_branch=record.target_branch,
                status=record.status,
                updated_at=record.updated_at.isoformat(),
                summary=record.latest_summary,
                final_message=record.latest_agent_message,
                touched_paths=json.loads(record.touched_paths_json or "[]"),
            )
            for record in records
        ]
    )
