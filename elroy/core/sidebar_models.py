"""Read models and actions for the Textual sidebar."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from ..db.db_models import AgendaItem, CodexSession, EmbeddableSqlModel
from ..io.completions import do_build_completions, do_get_memory_panel_entries
from ..repository.agenda.file_storage import get_checklist, read_agenda_metadata
from ..repository.codex_sessions.store import CodexSessionStore
from ..repository.feature_requests.queries import (
    get_feature_request,
    is_active_feature_request,
    list_feature_requests,
    list_self_reflection_feature_requests,
)
from ..repository.feature_requests.store import FeatureRequestRecord, update_feature_request
from ..repository.memories.factory import build_memory_lifecycle_orchestrator
from ..repository.memories.queries import do_db_get_memory_source_by_name
from ..repository.reminders.factory import build_reminder_orchestrator
from ..repository.tasks.factory import build_task_mutation_orchestrator
from ..repository.tasks.queries import do_get_active_tasks, do_get_task_by_name
from ..utils.clock import db_time_to_local, ensure_utc, utc_now
from .ctx import ElroyConfig
from .session import open_turn_context
from .turn import ElroySession, TurnContext

SidebarEntryKind = Literal["memory", "agenda", "feature_request", "codex_session"]


@dataclass(frozen=True)
class SidebarEntryRef:
    kind: SidebarEntryKind
    key: str
    source_type: str | None = None


@dataclass(frozen=True)
class SidebarEntry:
    title: str
    ref: SidebarEntryRef
    content: str
    deletable: bool = False


@dataclass(frozen=True)
class SidebarState:
    memories: list[SidebarEntry]
    agenda: list[SidebarEntry]
    improvements: list[SidebarEntry]
    feature_requests: list[SidebarEntry]
    codex_sessions: list[SidebarEntry]
    completions: list[str]


@dataclass(frozen=True)
class DetailModalSpec:
    title: str
    content: str
    ref: SidebarEntryRef
    can_delete: bool = False
    can_complete: bool = False


class SidebarBuilder:
    """Build read models for sidebar lists and detail modals."""

    MEMORY_BUFFER_SOURCE_TYPES: ClassVar[set[str]] = {"Memory", "ContextMessageSet"}

    def __init__(self, ctx: ElroyConfig, session: ElroySession):
        self.ctx = ctx
        self.session = session

    def build_sidebar_state(self) -> SidebarState:
        with open_turn_context(self.ctx, self.session) as turn:
            return SidebarState(
                memories=self._build_memory_entries(turn),
                agenda=self._build_agenda_entries(turn),
                improvements=self._build_improvement_entries(),
                feature_requests=self._build_feature_request_entries(),
                codex_sessions=self._build_codex_session_entries(turn),
                completions=do_build_completions(turn),
            )

    def build_detail_modal(self, entry: SidebarEntry) -> DetailModalSpec | None:
        with open_turn_context(self.ctx, self.session) as turn:
            if entry.ref.kind == "memory":
                return self._build_memory_detail_modal(turn, entry)
            if entry.ref.kind == "feature_request":
                return self._build_feature_request_detail_modal(entry)
            if entry.ref.kind == "codex_session":
                return self._build_codex_session_detail_modal(turn, entry)
            return self._build_agenda_detail_modal(turn, entry)

    def _build_memory_entries(self, turn: TurnContext) -> list[SidebarEntry]:
        memory_entries: list[SidebarEntry] = []
        for display_name, type_key in do_get_memory_panel_entries(turn):
            source_type, _, _ = type_key.partition(": ")
            if source_type not in self.MEMORY_BUFFER_SOURCE_TYPES:
                continue
            memory_entries.append(
                SidebarEntry(
                    title=display_name,
                    ref=SidebarEntryRef(kind="memory", key=display_name, source_type=source_type),
                    content="",
                )
            )
            if len(memory_entries) >= 15:
                break
        return memory_entries

    def _format_agenda_title(self, item: AgendaItem) -> str:
        title = item.name
        if item.trigger_datetime:
            when = db_time_to_local(item.trigger_datetime).strftime("%Y-%m-%d %H:%M")
            title = f"{title} [{when}]"
            if ensure_utc(item.trigger_datetime) <= utc_now():
                title = f"{title} (Due)"
        return title

    def _build_agenda_entries(self, turn: TurnContext) -> list[SidebarEntry]:
        return [
            SidebarEntry(
                title=self._format_agenda_title(item),
                ref=SidebarEntryRef(kind="agenda", key=item.name),
                content=item.to_fact(),
                deletable=bool(item.trigger_datetime or item.trigger_context),
            )
            for item in do_get_active_tasks(turn)[:15]
        ]

    def _build_improvement_entries(self) -> list[SidebarEntry]:
        return [
            SidebarEntry(
                title=f"{record.title} ({record.status})",
                ref=SidebarEntryRef(kind="feature_request", key=record.request_id),
                content=record.summary,
            )
            for record in list_self_reflection_feature_requests(active_only=True)[:15]
        ]

    def _build_feature_request_entries(self) -> list[SidebarEntry]:
        return [
            SidebarEntry(
                title=f"{record.title} ({record.status})",
                ref=SidebarEntryRef(kind="feature_request", key=record.request_id),
                content=record.summary,
            )
            for record in list_feature_requests()[:15]
        ]

    def _build_codex_session_entries(self, turn: TurnContext) -> list[SidebarEntry]:
        return [
            SidebarEntry(
                title=self._format_codex_session_title(record),
                ref=SidebarEntryRef(kind="codex_session", key=record.thread_id),
                content=record.latest_summary or record.latest_agent_message or "",
            )
            for record in CodexSessionStore(turn.db, turn.user_id).list_recent(limit=15)
        ]

    def _build_memory_detail_modal(self, turn: TurnContext, entry: SidebarEntry) -> DetailModalSpec | None:
        if entry.ref.source_type is None:
            return None
        source = do_db_get_memory_source_by_name(turn, entry.ref.source_type, entry.ref.key)
        if not source:
            return None

        return DetailModalSpec(
            title=entry.ref.key,
            content=source.to_fact(),
            ref=entry.ref,
            can_delete=isinstance(source, EmbeddableSqlModel),
        )

    def _build_feature_request_detail_modal(self, entry: SidebarEntry) -> DetailModalSpec | None:
        record = get_feature_request(entry.ref.key)
        if record is None:
            return None
        return DetailModalSpec(
            title=record.title,
            content=self._build_feature_request_modal_content(record),
            ref=entry.ref,
            can_complete=is_active_feature_request(record),
        )

    def _build_feature_request_modal_content(self, record: FeatureRequestRecord) -> str:
        source_label = self._format_feature_request_source(record.source)
        lines = [
            f"Status: {record.status}",
            f"Source: {source_label}",
            "",
            "Summary:",
            record.summary,
        ]
        if record.rationale:
            lines.extend(["", "Why It Matters:", record.rationale])
        if record.supporting_context:
            lines.extend(["", "Supporting Context:", record.supporting_context])
        return "\n".join(lines)

    def _format_feature_request_source(self, source: str) -> str:
        if source == "self_reflection":
            return "Self-reflection"
        return source.replace("_", " ").title()

    def _format_codex_session_title(self, record: CodexSession) -> str:
        repo_name = Path(record.repo_path).name or record.repo_path
        return f"{repo_name} ({record.status}) {record.thread_id}"

    def _build_codex_session_detail_modal(self, turn: TurnContext, entry: SidebarEntry) -> DetailModalSpec | None:
        record = CodexSessionStore(turn.db, turn.user_id).get_by_thread_id(entry.ref.key)
        if record is None:
            return None
        return DetailModalSpec(
            title=self._format_codex_session_title(record),
            content=self._build_codex_session_modal_content(record),
            ref=entry.ref,
        )

    def _build_codex_session_modal_content(self, record: CodexSession) -> str:
        lines = [
            f"Status: {record.status}",
            f"Updated: {record.updated_at.isoformat()}",
            f"Repo: {record.repo_path}",
        ]
        if record.worktree_path:
            lines.append(f"Worktree: {record.worktree_path}")
        if record.session_branch:
            lines.append(f"Session Branch: {record.session_branch}")
        if record.target_branch:
            lines.append(f"Target Branch: {record.target_branch}")
        if record.session_file_path:
            lines.append(f"Session File: {record.session_file_path}")

        lines.extend(["", "Summary:", record.latest_summary or "(No summary recorded.)"])
        if record.latest_agent_message:
            lines.extend(["", "Latest Agent Message:", record.latest_agent_message])
        return "\n".join(lines)

    def _build_agenda_modal_content(self, task: AgendaItem) -> str:
        metadata = read_agenda_metadata(Path(task.file_path))
        checklist = get_checklist(Path(task.file_path))
        lines: list[str] = []

        item_date = metadata.get("date")
        if item_date:
            lines.append(f"Date: {item_date}")
        if task.trigger_datetime:
            lines.append(f"Trigger Time: {task.trigger_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        if task.trigger_context:
            lines.append(f"Trigger Context: {task.trigger_context}")
        if task.status != "created":
            lines.append(f"Status: {task.status}")
        if task.closing_comment:
            lines.append(f"Closing Comment: {task.closing_comment}")
        if checklist:
            completed_count = sum(1 for item in checklist if item["completed"])
            lines.append(f"Checklist: {completed_count}/{len(checklist)} complete")

        body_lines = task.text.splitlines()
        if body_lines and body_lines[0].strip() == task.name.strip():
            body_lines = body_lines[1:]
            while body_lines and not body_lines[0].strip():
                body_lines = body_lines[1:]
        body = "\n".join(body_lines).strip()
        if body:
            lines.append(body)
        return "\n\n".join(lines) if lines else task.text

    def _build_agenda_detail_modal(self, turn: TurnContext, entry: SidebarEntry) -> DetailModalSpec:
        title = entry.title
        content = entry.content
        can_complete = False
        task = do_get_task_by_name(turn, entry.ref.key)
        if task:
            title = task.name
            content = self._build_agenda_modal_content(task)
            can_complete = task.status == "created"

        return DetailModalSpec(
            title=title,
            content=content,
            ref=entry.ref,
            can_delete=entry.deletable,
            can_complete=can_complete,
        )


class SidebarActionOrchestrator:
    """Apply sidebar-triggered mutations."""

    def __init__(self, ctx: ElroyConfig, session: ElroySession):
        self.ctx = ctx
        self.session = session

    def delete(self, ref: SidebarEntryRef) -> None:
        with open_turn_context(self.ctx, self.session) as turn:
            if ref.kind == "memory":
                self._delete_memory(turn, ref)
                return
            if ref.kind == "feature_request":
                return
            build_reminder_orchestrator(turn).do_delete_due_item(ref.key)

    def complete(self, ref: SidebarEntryRef) -> None:
        if ref.kind == "agenda":
            with open_turn_context(self.ctx, self.session) as turn:
                build_task_mutation_orchestrator(turn).complete_task(ref.key)
            return
        if ref.kind == "feature_request":
            self._close_feature_request(ref)

    def _close_feature_request(self, ref: SidebarEntryRef) -> None:
        record = get_feature_request(ref.key)
        if record is None:
            return
        update_feature_request(record, status="closed")

    def _delete_memory(self, turn, ref: SidebarEntryRef) -> None:
        if ref.source_type is None:
            return
        source = do_db_get_memory_source_by_name(turn, ref.source_type, ref.key)
        if isinstance(source, EmbeddableSqlModel):
            build_memory_lifecycle_orchestrator(turn).mark_inactive(source)


AgendaPresenter = SidebarBuilder
ModalSpec = DetailModalSpec
