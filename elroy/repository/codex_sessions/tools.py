import hashlib
import json
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from ...core.constants import RecoverableToolError, tool
from ...core.session import clone_config, invoke_with_config
from ...core.turn import TurnContext
from ...messenger.messenger import process_message
from .store import CodexSessionStore, CodexSessionUpdate

CODEX_SESSION_SEARCH_ROOT = Path.home() / ".codex" / "sessions"
DEFAULT_CODEX_SESSION_LIMIT = 5
MAX_COMMAND_OUTPUT_CHARS = 400
AGENT_BRANCH = "agent"
WORKTREE_ROOT_DIRNAME = ".elroy-codex-worktrees"
_repo_locks_guard = threading.Lock()
_repo_locks: dict[str, threading.Lock] = {}


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
class SessionWorkspace:
    source_repo_root: Path
    worktree_root: Path
    session_branch: str
    target_branch: str
    agent_worktree: Path


@dataclass(frozen=True)
class ResultBuildContext:
    source_repo_root: Path
    worktree_root: Path
    before: RepoSnapshot
    session_branch: str | None = None
    target_branch: str | None = None


def _repo_lock(repo_root: Path) -> threading.Lock:
    key = str(repo_root.resolve())
    with _repo_locks_guard:
        lock = _repo_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _repo_locks[key] = lock
        return lock


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


def _development_root() -> Path:
    cwd = Path.cwd().resolve()
    if "development" in cwd.parts:
        idx = cwd.parts.index("development")
        return Path(*cwd.parts[: idx + 1])

    candidate = Path.home() / "development"
    if candidate.exists():
        return candidate.resolve()
    return cwd


def _ensure_within_root(target: Path, root: Path) -> Path:
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise RecoverableToolError(f"Path {target} is outside the development root {root}.") from exc
    return target


def _resolve_repo_path(repo_path: str | None) -> Path:
    development_root = _development_root().resolve()
    if repo_path is None or not repo_path.strip():
        candidate = Path.cwd().resolve()
    else:
        raw_path = Path(repo_path).expanduser()
        candidate = (development_root / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()
    _ensure_within_root(candidate, development_root)

    try:
        result = _run_subprocess(["git", "-C", str(candidate), "rev-parse", "--show-toplevel"])
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip() or (exc.stdout or "").strip() or str(exc)
        raise RecoverableToolError(f"Path {candidate} is not inside a Git repository: {stderr}") from exc

    repo_root = Path(result.stdout.strip()).resolve()
    return _ensure_within_root(repo_root, development_root)


def _repo_slug(repo_root: Path) -> str:
    digest = hashlib.sha1(str(repo_root).encode("utf-8")).hexdigest()[:10]
    return f"{repo_root.name}-{digest}"


def _worktree_root(repo_root: Path) -> Path:
    return _development_root().resolve() / WORKTREE_ROOT_DIRNAME / _repo_slug(repo_root)


def _agent_worktree_path(repo_root: Path) -> Path:
    return _worktree_root(repo_root) / AGENT_BRANCH


def _session_worktree_path(repo_root: Path, session_branch: str) -> Path:
    return _worktree_root(repo_root) / "sessions" / session_branch


def _git_branch_exists(repo_root: Path, branch_name: str) -> bool:
    result = _run_subprocess(["git", "-C", str(repo_root), "show-ref", "--verify", f"refs/heads/{branch_name}"], check=False)
    return result.returncode == 0


def _ensure_clean_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _ensure_agent_branch_workspace(repo_root: Path) -> tuple[str, Path]:
    agent_worktree = _agent_worktree_path(repo_root)
    lock = _repo_lock(repo_root)
    with lock:
        if not _git_branch_exists(repo_root, AGENT_BRANCH):
            _run_subprocess(["git", "-C", str(repo_root), "branch", AGENT_BRANCH, "HEAD"])
        if not agent_worktree.exists():
            _ensure_clean_parent(agent_worktree)
            _run_subprocess(["git", "-C", str(repo_root), "worktree", "add", str(agent_worktree), AGENT_BRANCH])
    return AGENT_BRANCH, agent_worktree


def _create_session_workspace(repo_root: Path) -> tuple[str, Path, str, Path]:
    target_branch, agent_worktree = _ensure_agent_branch_workspace(repo_root)
    session_branch = f"elroy-codex-{uuid.uuid4().hex[:12]}"
    session_worktree = _session_worktree_path(repo_root, session_branch)
    lock = _repo_lock(repo_root)
    with lock:
        _ensure_clean_parent(session_worktree)
        _run_subprocess(["git", "-C", str(repo_root), "worktree", "add", "-b", session_branch, str(session_worktree), target_branch])
    return session_branch, session_worktree, target_branch, agent_worktree


def _ensure_existing_session_workspace(repo_root: Path, session_branch: str, worktree_path: Path) -> tuple[str, Path]:
    target_branch, agent_worktree = _ensure_agent_branch_workspace(repo_root)
    if worktree_path.exists():
        return target_branch, agent_worktree
    lock = _repo_lock(repo_root)
    with lock:
        _ensure_clean_parent(worktree_path)
        _run_subprocess(["git", "-C", str(repo_root), "worktree", "add", str(worktree_path), session_branch])
    return target_branch, agent_worktree


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


def _build_summary(
    session_id: str,
    workspace: ResultBuildContext,
    touched_paths: list[str],
    dirty_before: list[str],
    dirty_after: list[str],
    final_message: str,
    merge_note: str | None = None,
) -> str:
    lines = [f"Codex session {session_id} ran in isolated worktree {workspace.worktree_root} for source repo {workspace.source_repo_root}."]
    if workspace.session_branch:
        lines.append(f"Session branch: {workspace.session_branch}")
    if workspace.target_branch:
        lines.append(f"Target agent branch: {workspace.target_branch}")
    if touched_paths:
        lines.append("Paths changed during this run: " + ", ".join(touched_paths[:10]))
    else:
        lines.append("No repository changes were detected during this run.")
    if dirty_before:
        lines.append("Repo was already dirty before run: " + ", ".join(dirty_before[:10]))
    if dirty_after:
        lines.append("Dirty paths after run: " + ", ".join(dirty_after[:10]))
    if merge_note:
        lines.append(merge_note)
    lines.append("Final message: " + final_message.strip())
    return "\n".join(lines)


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


def _build_codex_args(prompt: str, repo_root: Path, *, session_id: str | None = None, model: str | None = None) -> list[str]:
    if session_id:
        args = ["codex", "exec", "resume", "--json", "--dangerously-bypass-approvals-and-sandbox", session_id, prompt]
    else:
        args = ["codex", "exec", "--json", "--dangerously-bypass-approvals-and-sandbox", "-C", str(repo_root), prompt]
    if model:
        args[3:3] = ["-m", model]
    return args


def _build_running_result(
    session_id: str,
    workspace: SessionWorkspace,
    before: RepoSnapshot,
) -> CodexSessionResult:
    dirty_before = sorted(before.status_by_path)
    return CodexSessionResult(
        session_id=session_id,
        repo_path=str(workspace.source_repo_root),
        worktree_path=str(workspace.worktree_root),
        session_branch=workspace.session_branch,
        target_branch=workspace.target_branch,
        status="running",
        final_message="",
        summary=(
            f"Codex session {session_id} is running asynchronously in isolated worktree {workspace.worktree_root} "
            f"on branch {workspace.session_branch}, targeting {workspace.target_branch} "
            f"for source repo {workspace.source_repo_root}."
        ),
        touched_paths=[],
        dirty_paths_before=dirty_before,
        dirty_paths_after=dirty_before,
        commands=[],
        session_file_path=None,
        resume_command=f"codex resume {session_id} -C {workspace.worktree_root}",
        running_in_background=True,
    )


def _build_failed_result(
    session_id: str,
    context: ResultBuildContext,
    stderr: str,
) -> CodexSessionResult:
    dirty_before = sorted(context.before.status_by_path)
    message = stderr.strip() or "Codex run failed."
    return CodexSessionResult(
        session_id=session_id,
        repo_path=str(context.source_repo_root),
        worktree_path=str(context.worktree_root),
        session_branch=context.session_branch,
        target_branch=context.target_branch,
        status="failed",
        final_message=message,
        summary=f"Codex session {session_id} failed in isolated worktree {context.worktree_root}: {message}",
        touched_paths=[],
        dirty_paths_before=dirty_before,
        dirty_paths_after=dirty_before,
        commands=[],
        session_file_path=None,
        resume_command=f"codex resume {session_id} -C {context.worktree_root}",
    )


def _build_result_from_stdout(
    stdout: str,
    context: ResultBuildContext,
    merge_note: str | None = None,
    status: str = "completed",
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
        merge_note=merge_note,
    )
    return CodexSessionResult(
        session_id=resolved_session_id,
        repo_path=str(context.source_repo_root),
        worktree_path=str(context.worktree_root),
        session_branch=context.session_branch,
        target_branch=context.target_branch,
        status=status,
        final_message=final_message,
        summary=summary,
        touched_paths=touched_paths,
        dirty_paths_before=dirty_before,
        dirty_paths_after=dirty_after,
        commands=commands,
        session_file_path=_session_file_path(resolved_session_id),
        resume_command=f"codex resume {resolved_session_id} -C {context.worktree_root}",
    )


def _merge_session_branch_into_agent(
    source_repo_root: Path,
    agent_worktree: Path,
    session_branch: str,
    target_branch: str,
) -> tuple[str, str]:
    lock = _repo_lock(source_repo_root)
    with lock:
        try:
            _run_subprocess(["git", "-C", str(agent_worktree), "status", "--porcelain=v1"], check=False)
            _run_subprocess(["git", "-C", str(agent_worktree), "merge", "--no-ff", "--no-edit", session_branch])
        except subprocess.CalledProcessError as exc:
            _run_subprocess(["git", "-C", str(agent_worktree), "merge", "--abort"], check=False)
            stderr = (exc.stderr or "").strip() or (exc.stdout or "").strip() or str(exc)
            return "merge_failed", f"Merge into {target_branch} failed: {stderr}"
    return "completed", f"Merged session branch {session_branch} into {target_branch}."


def _worktree_has_uncommitted_changes(worktree_root: Path) -> bool:
    result = _run_subprocess(["git", "-C", str(worktree_root), "status", "--porcelain=v1", "-uall"], check=False)
    return bool(result.stdout.strip())


def _commit_session_worktree_if_needed(worktree_root: Path, session_branch: str) -> str | None:
    if not _worktree_has_uncommitted_changes(worktree_root):
        return None
    _run_subprocess(["git", "-C", str(worktree_root), "add", "-A"])
    _run_subprocess(["git", "-C", str(worktree_root), "commit", "-m", f"Elroy Codex session updates ({session_branch})"])
    return f"Committed unmerged worktree changes on {session_branch} before integration."


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
        f"Session branch: {result.session_branch or 'n/a'}\n"
        f"Target branch: {result.target_branch or 'n/a'}\n"
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


def _complete_codex_session_in_background(
    *,
    config,
    prompt: str,
    workspace: SessionWorkspace,
    before: RepoSnapshot,
    process: subprocess.Popen[str],
    initial_stdout: str,
) -> None:
    stdout_tail, stderr_text = process.communicate()
    stdout = initial_stdout + (stdout_tail or "")
    result_context = ResultBuildContext(
        source_repo_root=workspace.source_repo_root,
        worktree_root=workspace.worktree_root,
        before=before,
        session_branch=workspace.session_branch,
        target_branch=workspace.target_branch,
    )

    try:
        if process.returncode not in {0, None}:
            session_id = _parse_thread_started(stdout) or "unknown"
            result = _build_failed_result(session_id, result_context, stderr_text or stdout)
        else:
            result = _build_result_from_stdout(stdout, result_context)
            commit_note = _commit_session_worktree_if_needed(workspace.worktree_root, workspace.session_branch)
            merge_status, merge_note = _merge_session_branch_into_agent(
                workspace.source_repo_root,
                workspace.agent_worktree,
                workspace.session_branch,
                workspace.target_branch,
            )
            notes = [note for note in (commit_note, merge_note) if note]
            result.status = merge_status
            if notes:
                result.summary = "\n".join([result.summary, *notes])
    except Exception as exc:
        session_id = _parse_thread_started(stdout) or "unknown"
        result = _build_failed_result(session_id, result_context, str(exc))

    new_ctx = clone_config(config)
    invoke_with_config(_persist_background_codex_result, new_ctx, prompt, result.model_dump_json())


def _prepare_codex_async_run(
    prompt: str,
    source_repo_root: Path,
    turn: TurnContext,
    *,
    workspace: SessionWorkspace | None = None,
    session_id: str | None = None,
    model: str | None = None,
) -> tuple[CodexSessionResult, threading.Thread]:
    if workspace is None:
        session_branch, worktree_root, target_branch, agent_worktree = _create_session_workspace(source_repo_root)
        workspace = SessionWorkspace(
            source_repo_root=source_repo_root,
            worktree_root=worktree_root,
            session_branch=session_branch,
            target_branch=target_branch,
            agent_worktree=agent_worktree,
        )

    before = _snapshot_repo(workspace.worktree_root)
    args = _build_codex_args(prompt, workspace.worktree_root, session_id=session_id, model=model)

    try:
        process = subprocess.Popen(
            args,
            cwd=str(workspace.worktree_root),
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

    running_result = _build_running_result(resolved_session_id, workspace, before)

    background_thread = threading.Thread(
        target=_complete_codex_session_in_background,
        kwargs={
            "config": turn.config,
            "prompt": prompt,
            "workspace": workspace,
            "before": before,
            "process": process,
            "initial_stdout": "".join(initial_stdout_lines),
        },
        daemon=True,
        name=f"codex-session-{resolved_session_id}",
    )
    return running_result, background_thread


@tool
def dispatch_codex_session(prompt: str, turn: TurnContext, repo_path: str | None = None, model: str | None = None) -> CodexSessionResult:
    """Run a Codex coding session against a repository inside the development workspace.

    Use this when you want Codex to work in another repository or to perform a bounded coding task
    in the current repo. Elroy will capture the Codex session id, summarize repository changes, and
    remember the session for later resumption.

    Args:
        prompt: Instructions to send to Codex.
        turn: Active turn context for persistence.
        repo_path: Repository path relative to the development directory, or an absolute path inside it.
        model: Optional Codex model override.
    """
    source_repo_root = _resolve_repo_path(repo_path)
    result, background_thread = _prepare_codex_async_run(prompt, source_repo_root, turn, model=model)
    _store_result(turn, prompt, result)
    background_thread.start()
    return result


@tool
def resume_codex_session(session_id: str, prompt: str, turn: TurnContext, model: str | None = None) -> CodexSessionResult:
    """Resume a previously recorded Codex session with a follow-up prompt.

    Use this after `dispatch_codex_session` when you want Codex to continue earlier work while
    preserving its own session context. Elroy resumes the same Codex thread id and returns an
    updated repository-change summary.

    Args:
        session_id: Existing Codex thread/session id returned by Elroy.
        prompt: Follow-up prompt to send to the existing Codex session.
        turn: Active turn context for persistence.
        model: Optional Codex model override.
    """
    store = CodexSessionStore(turn.db, turn.user_id)
    record = store.get_by_thread_id(session_id)
    if record is None:
        raise RecoverableToolError(f"Unknown Codex session '{session_id}'. Use list_codex_sessions to inspect available sessions.")
    if record.status == "running":
        raise RecoverableToolError(f"Codex session '{session_id}' is still running.")

    source_repo_root = Path(record.repo_path)
    if not record.session_branch or not record.worktree_path:
        raise RecoverableToolError(f"Codex session '{session_id}' is missing branch/worktree metadata and cannot be resumed.")
    target_branch, agent_worktree = _ensure_existing_session_workspace(
        source_repo_root,
        record.session_branch,
        Path(record.worktree_path),
    )
    workspace = SessionWorkspace(
        source_repo_root=source_repo_root,
        worktree_root=Path(record.worktree_path),
        session_branch=record.session_branch,
        target_branch=target_branch,
        agent_worktree=agent_worktree,
    )
    result, background_thread = _prepare_codex_async_run(
        prompt,
        source_repo_root,
        turn,
        workspace=workspace,
        session_id=session_id,
        model=model,
    )
    _store_result(turn, prompt, result)
    background_thread.start()
    return result


@tool
def list_codex_sessions(
    turn: TurnContext, repo_path: str | None = None, limit: int = DEFAULT_CODEX_SESSION_LIMIT
) -> CodexSessionListResult:
    """List recently recorded Codex sessions and their latest change summaries.

    Use this to discover resumable Codex sessions, inspect which repository each session targeted,
    and review the latest summary before deciding whether to resume one. Session listings include
    the isolated worktree and branch metadata so concurrent runs can be distinguished safely.

    Args:
        turn: Active turn context for persistence.
        repo_path: Optional repository path filter relative to the development directory.
        limit: Maximum number of sessions to return.
    """
    if limit < 1:
        raise RecoverableToolError("limit must be at least 1")

    repo_root = _resolve_repo_path(repo_path) if repo_path else None
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
