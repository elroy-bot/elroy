import json
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import desc, select

from ...db.db_models import CodexSession
from ...db.db_session import DbSession
from ...utils.clock import utc_now


@dataclass(frozen=True)
class CodexSessionUpdate:
    repo_path: Path
    worktree_path: Path | None
    session_branch: str | None
    target_branch: str | None
    prompt: str
    summary: str
    agent_message: str
    status: str
    commands: list[dict[str, str | int | None]]
    touched_paths: list[str]
    dirty_paths_before: list[str]
    dirty_paths_after: list[str]
    session_file_path: str | None


class CodexSessionStore:
    def __init__(self, db: DbSession, user_id: int):
        self.db = db
        self.user_id = user_id

    def get_by_thread_id(self, thread_id: str) -> CodexSession | None:
        return self.db.exec(select(CodexSession).where(CodexSession.user_id == self.user_id, CodexSession.thread_id == thread_id)).first()

    def list_recent(self, *, repo_path: Path | None = None, limit: int = 5) -> list[CodexSession]:
        stmt = select(CodexSession).where(CodexSession.user_id == self.user_id)
        if repo_path is not None:
            stmt = stmt.where(CodexSession.repo_path == str(repo_path))
        stmt = stmt.order_by(desc(CodexSession.updated_at)).limit(limit)
        return list(self.db.exec(stmt).all())

    def upsert(self, thread_id: str, update: CodexSessionUpdate) -> CodexSession:
        record = self.get_by_thread_id(thread_id)
        now = utc_now()
        if record is None:
            record = CodexSession(
                user_id=self.user_id,
                thread_id=thread_id,
                repo_path=str(update.repo_path),
                worktree_path=str(update.worktree_path) if update.worktree_path else None,
                session_branch=update.session_branch,
                target_branch=update.target_branch,
                latest_prompt=update.prompt,
                latest_summary=update.summary,
                latest_agent_message=update.agent_message,
                status=update.status,
                command_count=len(update.commands),
                commands_json=json.dumps(update.commands),
                touched_paths_json=json.dumps(update.touched_paths),
                dirty_paths_before_json=json.dumps(update.dirty_paths_before),
                dirty_paths_after_json=json.dumps(update.dirty_paths_after),
                session_file_path=update.session_file_path,
            )
            return self.db.persist(record)

        record.repo_path = str(update.repo_path)
        record.worktree_path = str(update.worktree_path) if update.worktree_path else None
        record.session_branch = update.session_branch
        record.target_branch = update.target_branch
        record.latest_prompt = update.prompt
        record.latest_summary = update.summary
        record.latest_agent_message = update.agent_message
        record.status = update.status
        record.command_count = len(update.commands)
        record.commands_json = json.dumps(update.commands)
        record.touched_paths_json = json.dumps(update.touched_paths)
        record.dirty_paths_before_json = json.dumps(update.dirty_paths_before)
        record.dirty_paths_after_json = json.dumps(update.dirty_paths_after)
        record.session_file_path = update.session_file_path
        record.updated_at = now
        return self.db.persist(record)
