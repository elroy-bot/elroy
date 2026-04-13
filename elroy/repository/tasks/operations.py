from pathlib import Path
from typing import Any

from ...core.services.task_service import TaskOperationService
from ...db.db_models import AgendaItem
from ...db.db_session import DbSession


def task_operation_service(
    db: DbSession,
    user_id: int,
    *,
    sync_embedding=None,
    remove_from_context_fn=None,
) -> TaskOperationService:
    return TaskOperationService(
        db,
        user_id,
        sync_embedding=sync_embedding,
        remove_from_context=remove_from_context_fn,
    )


def create_task(
    operation_service: TaskOperationService,
    name: str,
    text: str,
    *,
    item_date=None,
    trigger_datetime=None,
    trigger_context=None,
    allow_past_trigger: bool = False,
) -> AgendaItem:
    return operation_service.create_task(
        name,
        text,
        item_date=item_date,
        trigger_datetime=trigger_datetime,
        trigger_context=trigger_context,
        allow_past_trigger=allow_past_trigger,
    )


def complete_task(operation_service: TaskOperationService, task_name: str, closing_comment: str | None = None) -> AgendaItem:
    return operation_service.complete_task(task_name, closing_comment)


def delete_task(
    operation_service: TaskOperationService, task_name: str, closing_comment: str | None = None, *, delete_file: bool = False
) -> AgendaItem:
    return operation_service.delete_task(task_name, closing_comment, delete_file=delete_file)


def rename_task(operation_service: TaskOperationService, old_name: str, new_name: str) -> AgendaItem:
    return operation_service.rename_task(old_name, new_name)


def update_task_text(operation_service: TaskOperationService, task_name: str, new_text: str) -> AgendaItem:
    return operation_service.update_task_text(task_name, new_text)


def task_path(task: AgendaItem) -> Path:
    return TaskOperationService.task_path(task)


def get_task_body(task: AgendaItem) -> str:
    return TaskOperationService.get_task_body(task)


def get_task_metadata(task: AgendaItem) -> dict[str, Any]:
    return TaskOperationService.get_task_metadata(task)
