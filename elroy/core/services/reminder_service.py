from datetime import datetime

from rich.table import Table
from sqlmodel import col, select

from ...core.constants import RecoverableToolError
from ...core.logging import get_logger
from ...db.db_models import AgendaItem
from ...db.db_session import DbSession
from ...repository.context_messages.data_models import ContextMessage
from ...repository.context_messages.tools import to_synthetic_tool_call
from ...utils.clock import db_time_to_local, utc_now
from ...utils.utils import is_blank
from .task_service import TaskAlreadyExistsError, TaskOperationService, TaskQueryService

logger = get_logger()

DueItemLike = AgendaItem


class DueItemAlreadyExistsError(RecoverableToolError):
    def __init__(self, item_name: str, item_type: str):
        super().__init__(f"{item_type} due item '{item_name}' already exists")


class ReminderQueryService:
    def __init__(self, db: DbSession, user_id: int, *, task_queries: TaskQueryService | None = None):
        self.db = db
        self.user_id = user_id
        self.task_queries = task_queries or TaskQueryService(db, user_id)

    def get_db_due_item_by_name(self, name: str) -> DueItemLike | None:
        task = self.task_queries.get_task_by_name(name)
        if task and (task.trigger_datetime or task.trigger_context):
            return task
        return None

    def get_active_due_items(self) -> list[DueItemLike]:
        return list(self.task_queries.get_triggered_tasks())

    def get_due_items(self, include_completed: bool = False) -> list[DueItemLike]:
        if not include_completed:
            return self.get_active_due_items()

        return list(
            self.db.exec(
                select(AgendaItem).where(
                    AgendaItem.user_id == self.user_id,
                    col(AgendaItem.status).in_(["created", "completed"]),
                    ((col(AgendaItem.trigger_datetime).is_not(None)) | (col(AgendaItem.trigger_context).is_not(None))),
                )
            ).all()
        )

    def get_active_due_item_names(self) -> list[str]:
        return [item.name for item in self.get_active_due_items()]

    def get_due_timed_items(self) -> list[DueItemLike]:
        return list(self.task_queries.get_due_tasks())

    def get_due_item_by_name(self, item_name: str) -> str | None:
        due_item = self.get_db_due_item_by_name(item_name)
        return due_item.text if due_item else None

    def print_due_items(self, active: bool, n: int | None = None) -> Table | str:
        due_items = [item for item in self.get_due_items(include_completed=not active) if bool(item.is_active) == active]

        if not due_items:
            status = "active" if active else "inactive"
            return f"No {status} due items found."

        title = "Active Due Items" if active else "Inactive Due Items"
        table = Table(title=title, show_lines=True)
        table.add_column("Name", justify="left", style="cyan", no_wrap=True)
        table.add_column("Type", justify="left", style="yellow")
        table.add_column("Trigger Time", justify="left", style="green")
        table.add_column("Context", justify="left", style="green")
        table.add_column("Text", justify="left", style="green")
        table.add_column("Created At", justify="left", style="green")

        for due_item in list(due_items)[:n]:
            item_type = "Timed" if due_item.trigger_datetime else "Contextual"
            trigger_time = db_time_to_local(due_item.trigger_datetime).strftime("%Y-%m-%d %H:%M:%S") if due_item.trigger_datetime else "N/A"
            context = due_item.trigger_context or "N/A"
            table.add_row(
                due_item.name,
                item_type,
                trigger_time,
                context,
                due_item.text,
                db_time_to_local(due_item.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            )
        return table

    def get_due_item_context_msgs(self) -> list[ContextMessage]:
        due_items = self.get_due_timed_items()
        if not due_items:
            return []

        lines: list[str] = []
        for due_item in due_items:
            trigger_dt = due_item.trigger_datetime
            if not trigger_dt:
                continue
            lines.append(
                f"⏰ DUE ITEM: '{due_item.name}' - {due_item.text}\n\nThis item was scheduled for {trigger_dt.strftime('%Y-%m-%d %H:%M:%S')} and is now due. Please inform the user about it and then use the delete_due_item tool to remove it from active due items."
            )
        return to_synthetic_tool_call("get_due_items", "\n".join(lines))


class ReminderOperationService:
    def __init__(
        self,
        db: DbSession,
        user_id: int,
        *,
        task_operations: TaskOperationService | None = None,
        reminder_queries: ReminderQueryService | None = None,
    ):
        self.db = db
        self.user_id = user_id
        self.reminder_queries = reminder_queries or ReminderQueryService(db, user_id)
        self.task_operations = task_operations or TaskOperationService(db, user_id)

    def create_onboarding_due_item(self, preferred_name: str) -> None:
        self.create_due_item(
            name=f"Introduce myself to {preferred_name}",
            text="Introduce myself - a few things that make me unique are my ability to form long term memories, and the ability to create due items that surface at the right time or context",
            trigger_context="When user logs in for the first time",
        )

    def create_due_item(
        self,
        name: str,
        text: str,
        trigger_time: datetime | None = None,
        trigger_context: str | None = None,
    ) -> AgendaItem:
        if is_blank(name):
            raise ValueError("Due item name cannot be empty")
        if not trigger_time and not trigger_context:
            raise RecoverableToolError("Either trigger_time or trigger_context must be provided for due items")
        if trigger_time and trigger_time < utc_now():
            raise RecoverableToolError(
                f"Attempted to create a due item for {trigger_time}, which is in the past. The current time is {utc_now()}"
            )

        if self.reminder_queries.get_db_due_item_by_name(name):
            item_type = "Timed" if trigger_time else "Contextual"
            raise DueItemAlreadyExistsError(name, item_type)

        try:
            return self.task_operations.create_task(
                name,
                text,
                trigger_datetime=trigger_time,
                trigger_context=trigger_context,
            )
        except TaskAlreadyExistsError as e:
            item_type = "Timed" if trigger_time else "Contextual"
            raise DueItemAlreadyExistsError(name, item_type) from e

    def complete_due_item(self, item_name: str, closing_comment: str | None = None) -> str:
        due_item = self.reminder_queries.get_db_due_item_by_name(item_name)
        if not due_item:
            active_names = self.reminder_queries.get_active_due_item_names()
            raise RecoverableToolError(f"Active due item '{item_name}' not found. Active due items: {', '.join(active_names)}")

        logger.info(f"Completing agenda-backed due item {item_name} for user {self.user_id}")
        self.task_operations.complete_task(item_name, closing_comment)

        if closing_comment:
            return f"Due item '{item_name}' has been marked as completed. Comment: {closing_comment}"
        return f"Due item '{item_name}' has been marked as completed."

    def delete_due_item(self, item_name: str, closing_comment: str | None = None) -> str:
        due_item = self.reminder_queries.get_db_due_item_by_name(item_name)
        if not due_item:
            active_names = self.reminder_queries.get_active_due_item_names()
            raise RecoverableToolError(f"Active due item '{item_name}' not found. Active due items: {', '.join(active_names)}")

        logger.info(f"Deleting agenda-backed due item {item_name} for user {self.user_id}")
        self.task_operations.delete_task(item_name, closing_comment)

        if closing_comment:
            return f"Due item '{item_name}' has been deleted. Comment: {closing_comment}"
        return f"Due item '{item_name}' has been deleted."
