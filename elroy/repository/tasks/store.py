from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

from sqlmodel import select

from ...config.paths import get_agenda_dir
from ...core.constants import RecoverableToolError
from ...db.db_models import AgendaItem
from ...db.db_session import DbSession
from ...utils.clock import utc_now
from ...utils.utils import is_blank
from ..agenda.file_storage import (
    AgendaFileMetadata,
    get_agenda_file_path,
    read_agenda_metadata,
    update_agenda_body,
    update_agenda_metadata,
    write_agenda_item_with_metadata,
)
from ..file_utils import read_file_text


class TaskAlreadyExistsError(RecoverableToolError):
    def __init__(self, task_name: str):
        super().__init__(f"Task '{task_name}' already exists")


class TaskStore:
    def __init__(self, db: DbSession, user_id: int):
        self.db = db
        self.user_id = user_id

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
        if get_task_by_name_for_service(self.db, self.user_id, name):
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
        return self.db.persist(
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

    def complete_task(self, task_name: str, closing_comment: str | None = None) -> AgendaItem:
        task = get_task_by_name_for_service(self.db, self.user_id, task_name)
        if not task:
            raise RecoverableToolError(f"Active task '{task_name}' not found.")
        if task.status == "completed":
            return task

        task.status = "completed"
        task.is_active = False
        task.closing_comment = closing_comment
        task.updated_at = utc_now()
        task = self.db.persist(task)
        update_agenda_metadata(task_path(task), {"completed": True, "status": "completed", "closing_comment": closing_comment})
        return task

    def delete_task(self, task_name: str, closing_comment: str | None = None, *, delete_file: bool = False) -> AgendaItem:
        task = get_task_by_name_for_service(self.db, self.user_id, task_name)
        if not task:
            raise RecoverableToolError(f"Active task '{task_name}' not found.")

        task.status = "deleted"
        task.is_active = None
        task.closing_comment = closing_comment
        task.updated_at = utc_now()
        task = self.db.persist(task)
        update_agenda_metadata(task_path(task), {"status": "deleted", "closing_comment": closing_comment})
        if delete_file:
            task_path(task).unlink(missing_ok=True)
        return task

    def rename_task(self, old_name: str, new_name: str) -> AgendaItem:
        task = get_task_by_name_for_service(self.db, self.user_id, old_name)
        if not task:
            raise RecoverableToolError(f"Active task '{old_name}' not found.")
        if get_task_by_name_for_service(self.db, self.user_id, new_name):
            raise RecoverableToolError(f"Active task '{new_name}' already exists.")

        current_path = task_path(task)
        target_path = get_agenda_file_path(current_path.parent, new_name)
        current_path.rename(target_path)
        task.name = new_name
        task.file_path = str(target_path)
        task.updated_at = utc_now()
        return self.db.persist(task)

    def update_task_text(self, task_name: str, new_text: str) -> AgendaItem:
        task = get_task_by_name_for_service(self.db, self.user_id, task_name)
        if not task:
            raise RecoverableToolError(f"Active task '{task_name}' not found.")
        update_agenda_body(task_path(task), new_text)
        task.updated_at = utc_now()
        return self.db.persist(task)


def get_task_by_name_for_service(db: DbSession, user_id: int, task_name: str) -> AgendaItem | None:
    return db.exec(
        select(AgendaItem).where(AgendaItem.user_id == user_id, AgendaItem.name == task_name, cast(Any, AgendaItem.is_active))
    ).first()


def task_path(task: AgendaItem) -> Path:
    return Path(task.file_path)


def get_task_body(task: AgendaItem) -> str:
    return read_file_text(task_path(task)).strip()


def get_task_metadata(task: AgendaItem) -> dict:
    return read_agenda_metadata(task_path(task))
