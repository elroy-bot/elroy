"""Presentation helpers for the Textual sidebar and item modals."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from ...core.ctx import ElroyContext
from ...core.services.reminder_service import ReminderOperationService
from ...core.services.task_service import TaskOperationService, TaskQueryService
from ...db.db_models import AgendaItem, EmbeddableSqlModel
from ...io.completions import build_completions, get_memory_panel_entries
from ...repository.agenda.file_storage import get_checklist, read_agenda_metadata
from ...repository.memories.operations import mark_inactive
from ...repository.memories.queries import db_get_memory_source_by_name
from ...repository.recall.operations import remove_from_context, upsert_embedding_if_needed
from ...utils.clock import db_time_to_local, ensure_utc, utc_now


@dataclass
class SidebarEntry:
    title: str
    lookup_key: str
    content: str
    deletable: bool = False


@dataclass
class SidebarState:
    memories: list[SidebarEntry]
    agenda: list[SidebarEntry]
    completions: list[str]


@dataclass
class ModalSpec:
    title: str
    content: str
    on_delete: Callable[[], None] | None = None
    on_complete: Callable[[], None] | None = None


class AgendaPresenter:
    MEMORY_BUFFER_SOURCE_TYPES: ClassVar[set[str]] = {"Memory", "DocumentExcerpt", "ContextMessageSet"}

    def __init__(self, ctx: ElroyContext):
        self.ctx = ctx

    def _task_queries(self) -> TaskQueryService:
        return TaskQueryService(self.ctx.db, self.ctx.user_id)

    def _task_operations(self) -> TaskOperationService:
        return TaskOperationService(
            self.ctx.db,
            self.ctx.user_id,
            sync_embedding=lambda row: upsert_embedding_if_needed(self.ctx, row),
            remove_from_context=lambda row: remove_from_context(self.ctx, row),
        )

    def _reminder_operations(self) -> ReminderOperationService:
        return ReminderOperationService(
            self.ctx.db,
            self.ctx.user_id,
            task_operations=self._task_operations(),
        )

    def build_sidebar_state(self) -> SidebarState:
        memory_entries = self._build_memory_entries()
        agenda_entries = self._build_agenda_entries()
        return SidebarState(
            memories=memory_entries,
            agenda=agenda_entries,
            completions=build_completions(self.ctx),
        )

    def _build_memory_entries(self) -> list[SidebarEntry]:
        memory_entries: list[SidebarEntry] = []
        for display_name, type_key in get_memory_panel_entries(self.ctx):
            source_type, _, _ = type_key.partition(": ")
            if source_type not in self.MEMORY_BUFFER_SOURCE_TYPES:
                continue
            memory_entries.append(SidebarEntry(title=display_name, lookup_key=type_key, content=""))
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

    def _build_agenda_entries(self) -> list[SidebarEntry]:
        return [
            SidebarEntry(
                title=self._format_agenda_title(item),
                lookup_key=item.name,
                content=item.to_fact(),
                deletable=bool(item.trigger_datetime or item.trigger_context),
            )
            for item in self._task_queries().get_active_tasks()[:15]
        ]

    def build_memory_modal(self, entry: SidebarEntry, refresh: Callable[[], None]) -> ModalSpec | None:
        if ": " not in entry.lookup_key:
            return None
        source_type, name = entry.lookup_key.split(": ", 1)
        source = db_get_memory_source_by_name(self.ctx, source_type, name)
        if not source:
            return None

        on_delete = None
        if isinstance(source, EmbeddableSqlModel):

            def on_delete(s=source) -> None:
                mark_inactive(self.ctx, s)
                refresh()

        return ModalSpec(title=name, content=source.to_fact(), on_delete=on_delete)

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

    def build_agenda_modal(self, entry: SidebarEntry, refresh: Callable[[], None]) -> ModalSpec:
        title = entry.title
        content = entry.content
        on_delete = None
        on_complete = None
        task = self._task_queries().get_task_by_name(entry.lookup_key)
        if task:
            title = task.name
            content = self._build_agenda_modal_content(task)
            if task.status == "created":

                def on_complete(name=entry.lookup_key) -> None:
                    self._task_operations().complete_task(name)
                    refresh()

        if entry.deletable:

            def on_delete(name=entry.lookup_key) -> None:
                self._reminder_operations().delete_due_item(name)
                refresh()

        return ModalSpec(title=title, content=content, on_delete=on_delete, on_complete=on_complete)
