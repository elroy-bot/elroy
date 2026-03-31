from datetime import date, datetime
from pathlib import Path

from ...config.paths import get_agenda_dir
from ...core.constants import RecoverableToolError
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import AgendaItem
from ...utils.clock import utc_now
from ...utils.utils import is_blank
from ..agenda.file_storage import (
    get_agenda_file_path,
    read_agenda_metadata,
    update_agenda_body,
    update_agenda_metadata,
    write_agenda_item_with_metadata,
)
from ..file_utils import read_file_text
from ..recall.operations import remove_from_context, upsert_embedding_if_needed
from .queries import get_task_by_name

logger = get_logger()


class TaskAlreadyExistsError(RecoverableToolError):
    def __init__(self, task_name: str):
        super().__init__(f"Task '{task_name}' already exists")


def create_task(
    ctx: ElroyContext,
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
    if get_task_by_name(ctx, name):
        raise TaskAlreadyExistsError(name)

    target_date = item_date or date.today()
    path = write_agenda_item_with_metadata(
        get_agenda_dir(),
        name,
        text,
        target_date,
        trigger_datetime=trigger_datetime,
        trigger_context=trigger_context,
        status="created",
    )
    row = ctx.db.persist(
        AgendaItem(
            user_id=ctx.user_id,
            name=name,
            file_path=str(path),
            trigger_datetime=trigger_datetime,
            trigger_context=trigger_context,
            status="created",
            is_active=True,
        )
    )
    upsert_embedding_if_needed(ctx, row)
    return row


def complete_task(ctx: ElroyContext, task_name: str, closing_comment: str | None = None) -> AgendaItem:
    task = get_task_by_name(ctx, task_name)
    if not task:
        raise RecoverableToolError(f"Active task '{task_name}' not found.")
    if task.status == "completed":
        return task

    task.status = "completed"
    task.is_active = False
    task.closing_comment = closing_comment
    task.updated_at = utc_now()  # noqa: F841
    task = ctx.db.persist(task)
    update_agenda_metadata(task_path(task), {"completed": True, "status": "completed", "closing_comment": closing_comment})
    upsert_embedding_if_needed(ctx, task)
    return task


def delete_task(ctx: ElroyContext, task_name: str, closing_comment: str | None = None, *, delete_file: bool = False) -> AgendaItem:
    task = get_task_by_name(ctx, task_name)
    if not task:
        raise RecoverableToolError(f"Active task '{task_name}' not found.")

    task.status = "deleted"
    task.is_active = None
    task.closing_comment = closing_comment
    task.updated_at = utc_now()  # noqa: F841
    remove_from_context(ctx, task)
    task = ctx.db.persist(task)
    update_agenda_metadata(task_path(task), {"status": "deleted", "closing_comment": closing_comment})
    upsert_embedding_if_needed(ctx, task)
    if delete_file:
        task_path(task).unlink(missing_ok=True)
    return task


def rename_task(ctx: ElroyContext, old_name: str, new_name: str) -> AgendaItem:
    task = get_task_by_name(ctx, old_name)
    if not task:
        raise RecoverableToolError(f"Active task '{old_name}' not found.")
    if get_task_by_name(ctx, new_name):
        raise RecoverableToolError(f"Active task '{new_name}' already exists.")

    current_path = task_path(task)
    target_path = get_agenda_file_path(current_path.parent, new_name)
    current_path.rename(target_path)
    task.name = new_name
    task.file_path = str(target_path)
    task.updated_at = utc_now()  # noqa: F841
    task = ctx.db.persist(task)
    upsert_embedding_if_needed(ctx, task)
    return task


def update_task_text(ctx: ElroyContext, task_name: str, new_text: str) -> AgendaItem:
    task = get_task_by_name(ctx, task_name)
    if not task:
        raise RecoverableToolError(f"Active task '{task_name}' not found.")
    update_agenda_body(task_path(task), new_text)
    task.updated_at = utc_now()  # noqa: F841
    task = ctx.db.persist(task)
    upsert_embedding_if_needed(ctx, task)
    return task


def task_path(task: AgendaItem) -> Path:
    return Path(task.file_path)


def get_task_body(task: AgendaItem) -> str:
    return read_file_text(task_path(task)).strip()


def get_task_metadata(task: AgendaItem) -> dict:
    return read_agenda_metadata(task_path(task))
