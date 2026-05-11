import hashlib
import json
import subprocess
from pathlib import Path

from pydantic import BaseModel

from ...core.constants import RecoverableToolError, tool
from ...core.turn import TurnContext
from .store import CodexSessionStore, CodexSessionUpdate

CODEX_SESSION_SEARCH_ROOT = Path.home() / ".codex" / "sessions"
DEFAULT_CODEX_SESSION_LIMIT = 5
MAX_COMMAND_OUTPUT_CHARS = 400


class CodexCommandSummary(BaseModel):
    command: str
    exit_code: int | None = None
    output_excerpt: str = ""


class CodexSessionResult(BaseModel):
    session_id: str
    repo_path: str
    status: str
    final_message: str
    summary: str
    touched_paths: list[str]
    dirty_paths_before: list[str]
    dirty_paths_after: list[str]
    commands: list[CodexCommandSummary]
    session_file_path: str | None = None
    resume_command: str


class CodexSessionListEntry(BaseModel):
    session_id: str
    repo_path: str
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
    repo_root: Path,
    touched_paths: list[str],
    dirty_before: list[str],
    dirty_after: list[str],
    final_message: str,
) -> str:
    lines = [f"Codex session {session_id} ran in {repo_root}."]
    if touched_paths:
        lines.append("Paths changed during this run: " + ", ".join(touched_paths[:10]))
    else:
        lines.append("No repository changes were detected during this run.")
    if dirty_before:
        lines.append("Repo was already dirty before run: " + ", ".join(dirty_before[:10]))
    if dirty_after:
        lines.append("Dirty paths after run: " + ", ".join(dirty_after[:10]))
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


def _run_codex(prompt: str, repo_root: Path, *, session_id: str | None = None, model: str | None = None) -> CodexSessionResult:
    before = _snapshot_repo(repo_root)
    if session_id:
        args = ["codex", "exec", "resume", "--json", "--dangerously-bypass-approvals-and-sandbox", session_id, prompt]
    else:
        args = ["codex", "exec", "--json", "--dangerously-bypass-approvals-and-sandbox", "-C", str(repo_root), prompt]
    if model:
        args[3:3] = ["-m", model]

    try:
        result = _run_subprocess(args, cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip() or (exc.stdout or "").strip() or str(exc)
        raise RecoverableToolError(f"Codex run failed: {stderr}") from exc

    resolved_session_id, final_message, commands = _parse_codex_exec_output(result.stdout)
    after = _snapshot_repo(repo_root)
    touched_paths = _touched_paths(before, after)
    dirty_before = sorted(before.status_by_path)
    dirty_after = sorted(after.status_by_path)
    summary = _build_summary(resolved_session_id, repo_root, touched_paths, dirty_before, dirty_after, final_message)
    return CodexSessionResult(
        session_id=resolved_session_id,
        repo_path=str(repo_root),
        status="completed",
        final_message=final_message,
        summary=summary,
        touched_paths=touched_paths,
        dirty_paths_before=dirty_before,
        dirty_paths_after=dirty_after,
        commands=commands,
        session_file_path=_session_file_path(resolved_session_id),
        resume_command=f"codex resume {resolved_session_id} -C {repo_root}",
    )


def _store_result(turn: TurnContext, prompt: str, result: CodexSessionResult) -> None:
    CodexSessionStore(turn.db, turn.user_id).upsert(
        result.session_id,
        CodexSessionUpdate(
            repo_path=Path(result.repo_path),
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
    repo_root = _resolve_repo_path(repo_path)
    result = _run_codex(prompt, repo_root, model=model)
    _store_result(turn, prompt, result)
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

    result = _run_codex(prompt, Path(record.repo_path), session_id=session_id, model=model)
    _store_result(turn, prompt, result)
    return result


@tool
def list_codex_sessions(
    turn: TurnContext, repo_path: str | None = None, limit: int = DEFAULT_CODEX_SESSION_LIMIT
) -> CodexSessionListResult:
    """List recently recorded Codex sessions and their latest change summaries.

    Use this to discover resumable Codex sessions, inspect which repository each session targeted,
    and review the latest summary before deciding whether to resume one.

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
                status=record.status,
                updated_at=record.updated_at.isoformat(),
                summary=record.latest_summary,
                final_message=record.latest_agent_message,
                touched_paths=json.loads(record.touched_paths_json or "[]"),
            )
            for record in records
        ]
    )
