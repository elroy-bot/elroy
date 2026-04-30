"""Read models and actions for the Textual sidebar."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from ..db.db_models import AgendaItem, EmbeddableSqlModel
from ..io.completions import do_build_completions, do_get_memory_panel_entries
from ..repository.agenda.file_storage import get_checklist, read_agenda_metadata
from ..repository.memories.factory import build_memory_lifecycle_orchestrator
from ..repository.memories.queries import do_db_get_memory_source_by_name
from ..repository.reminders.factory import build_reminder_orchestrator
from ..repository.tasks.factory import build_task_mutation_orchestrator
from ..repository.tasks.queries import do_get_active_tasks, do_get_task_by_name
from ..utils.clock import db_time_to_local, ensure_utc, utc_now
from .ctx import ElroyConfig
from .session import open_turn_context
from .turn import ElroySession, TurnContext

SidebarEntryKind = Literal["memory", "agenda"]


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
                completions=do_build_completions(turn),
            )

    def build_detail_modal(self, entry: SidebarEntry) -> DetailModalSpec | None:
        with open_turn_context(self.ctx, self.session) as turn:
            if entry.ref.kind == "memory":
                return self._build_memory_detail_modal(turn, entry)
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
            build_reminder_orchestrator(turn).do_delete_due_item(ref.key)

    def complete(self, ref: SidebarEntryRef) -> None:
        if ref.kind != "agenda":
            return
        with open_turn_context(self.ctx, self.session) as turn:
            build_task_mutation_orchestrator(turn).complete_task(ref.key)

    def _delete_memory(self, turn, ref: SidebarEntryRef) -> None:
        if ref.source_type is None:
            return
        source = do_db_get_memory_source_by_name(turn, ref.source_type, ref.key)
        if isinstance(source, EmbeddableSqlModel):
            build_memory_lifecycle_orchestrator(turn).mark_inactive(source)


AgendaPresenter = SidebarBuilder
ModalSpec = DetailModalSpec
