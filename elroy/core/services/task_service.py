from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlmodel import col, select

from ...config.paths import get_agenda_dir
from ...core.constants import RecoverableToolError
from ...core.logging import get_logger
from ...db.db_models import AgendaItem
from ...db.db_session import DbSession
from ...repository.agenda.file_storage import (
    AgendaFileMetadata,
    get_agenda_file_path,
    read_agenda_metadata,
    update_agenda_body,
    update_agenda_metadata,
    write_agenda_item_with_metadata,
)
from ...repository.file_utils import read_file_text
from ...utils.clock import ensure_utc, utc_now
from ...utils.utils import is_blank

logger = get_logger()


class TaskAlreadyExistsError(RecoverableToolError):
    def __init__(self, task_name: str):
        super().__init__(f"Task '{task_name}' already exists")


class TaskQueryService:
    def __init__(self, db: DbSession, user_id: int):
        self.db = db
        self.user_id = user_id

    def get_task_by_name(self, name: str) -> AgendaItem | None:
        return self.db.exec(
            select(AgendaItem).where(
                AgendaItem.user_id == self.user_id,
                AgendaItem.name == name,
                col(AgendaItem.is_active).is_(True),
            )
        ).first()

    def get_active_tasks(self) -> list[AgendaItem]:
        return list(
            self.db.exec(
                select(AgendaItem)
                .where(
                    AgendaItem.user_id == self.user_id,
                    col(AgendaItem.is_active).is_(True),
                )
                .order_by(col(AgendaItem.created_at))
            ).all()
        )

    def get_triggered_tasks(self) -> list[AgendaItem]:
        return [task for task in self.get_active_tasks() if task.trigger_datetime or task.trigger_context]

    def get_due_tasks(self) -> list[AgendaItem]:
        now = utc_now()
        return [task for task in self.get_active_tasks() if task.trigger_datetime is not None and ensure_utc(task.trigger_datetime) <= now]

    def get_today_tasks(self) -> list[AgendaItem]:
        today = date.today().isoformat()
        return [task for task in self.get_active_tasks() if task.to_fact() and today in task.to_fact()]


class TaskOperationService:
    def __init__(
        self,
        db: DbSession,
        user_id: int,
        *,
        sync_embedding: Callable[[AgendaItem], None] | None = None,
        remove_from_context: Callable[[AgendaItem], None] | None = None,
        query_service: TaskQueryService | None = None,
    ):
        self.db = db
        self.user_id = user_id
        self.sync_embedding = sync_embedding
        self.remove_from_context = remove_from_context
        self.query_service = query_service or TaskQueryService(db, user_id)

    def create_task(
        self,
        name: str,
        text: str,
        *,
        item_date: date | None = None,
        trigger_datetime: datetime | None = None,
        trigger_context: str | None = None,
        allow_past_trigger: bool = False,
    ) -> AgendaItem:
        if is_blank(name):
            raise ValueError("Task name cannot be empty")
        if trigger_datetime and trigger_datetime < utc_now() and not allow_past_trigger:
            raise RecoverableToolError(
                f"Attempted to create a due item for {trigger_datetime}, which is in the past. The current time is {utc_now()}"
            )
        if self.query_service.get_task_by_name(name):
            raise TaskAlreadyExistsError(name)

        target_date = item_date or date.today()
        path = write_agenda_item_with_metadata(
            get_agenda_dir(),
            name,
            text,
            target_date,
            AgendaFileMetadata(
                trigger_datetime=trigger_datetime,
                trigger_context=trigger_context,
                status="created",
            ),
        )
        row = self.db.persist(
            AgendaItem(
                user_id=self.user_id,
                name=name,
                file_path=str(path),
                trigger_datetime=trigger_datetime,
                trigger_context=trigger_context,
                status="created",
                is_active=True,
            )
        )
        self._sync_embedding(row)
        return row

    def complete_task(self, task_name: str, closing_comment: str | None = None) -> AgendaItem:
        task = self.query_service.get_task_by_name(task_name)
        if not task:
            raise RecoverableToolError(f"Active task '{task_name}' not found.")
        if task.status == "completed":
            return task

        task.status = "completed"
        task.is_active = False
        task.closing_comment = closing_comment
        task.updated_at = utc_now()
        task = self.db.persist(task)
        update_agenda_metadata(self.task_path(task), {"completed": True, "status": "completed", "closing_comment": closing_comment})
        self._sync_embedding(task)
        return task

    def delete_task(self, task_name: str, closing_comment: str | None = None, *, delete_file: bool = False) -> AgendaItem:
        task = self.query_service.get_task_by_name(task_name)
        if not task:
            raise RecoverableToolError(f"Active task '{task_name}' not found.")

        task.status = "deleted"
        task.is_active = None
        task.closing_comment = closing_comment
        task.updated_at = utc_now()
        if self.remove_from_context:
            self.remove_from_context(task)
        task = self.db.persist(task)
        update_agenda_metadata(self.task_path(task), {"status": "deleted", "closing_comment": closing_comment})
        self._sync_embedding(task)
        if delete_file:
            self.task_path(task).unlink(missing_ok=True)
        return task

    def rename_task(self, old_name: str, new_name: str) -> AgendaItem:
        task = self.query_service.get_task_by_name(old_name)
        if not task:
            raise RecoverableToolError(f"Active task '{old_name}' not found.")
        if self.query_service.get_task_by_name(new_name):
            raise RecoverableToolError(f"Active task '{new_name}' already exists.")

        current_path = self.task_path(task)
        target_path = get_agenda_file_path(current_path.parent, new_name)
        current_path.rename(target_path)
        task.name = new_name
        task.file_path = str(target_path)
        task.updated_at = utc_now()
        task = self.db.persist(task)
        self._sync_embedding(task)
        return task

    def update_task_text(self, task_name: str, new_text: str) -> AgendaItem:
        task = self.query_service.get_task_by_name(task_name)
        if not task:
            raise RecoverableToolError(f"Active task '{task_name}' not found.")
        update_agenda_body(self.task_path(task), new_text)
        task.updated_at = utc_now()
        task = self.db.persist(task)
        self._sync_embedding(task)
        return task

    @staticmethod
    def task_path(task: AgendaItem) -> Path:
        return Path(task.file_path)

    @classmethod
    def get_task_body(cls, task: AgendaItem) -> str:
        return read_file_text(cls.task_path(task)).strip()

    @classmethod
    def get_task_metadata(cls, task: AgendaItem) -> dict[str, Any]:
        return read_agenda_metadata(cls.task_path(task))

    def _sync_embedding(self, task: AgendaItem) -> None:
        if self.sync_embedding:
            self.sync_embedding(task)
