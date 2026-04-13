from pathlib import Path
from typing import Any

from ...core.ctx import ElroyContext
from ...core.services.task_service import TaskOperationService
from ...db.db_models import AgendaItem
from ..recall.operations import remove_from_context, upsert_embedding_if_needed


def _task_operations(ctx: ElroyContext) -> TaskOperationService:
    return TaskOperationService(
        ctx.db,
        ctx.user_id,
        sync_embedding=lambda row: upsert_embedding_if_needed(ctx, row),
        remove_from_context=lambda row: remove_from_context(ctx, row),
    )


def create_task(
    ctx: ElroyContext,
    name: str,
    text: str,
    *,
    item_date=None,
    trigger_datetime=None,
    trigger_context=None,
    allow_past_trigger: bool = False,
) -> AgendaItem:
    return _task_operations(ctx).create_task(
        name,
        text,
        item_date=item_date,
        trigger_datetime=trigger_datetime,
        trigger_context=trigger_context,
        allow_past_trigger=allow_past_trigger,
    )


def complete_task(ctx: ElroyContext, task_name: str, closing_comment: str | None = None) -> AgendaItem:
    return _task_operations(ctx).complete_task(task_name, closing_comment)


def delete_task(ctx: ElroyContext, task_name: str, closing_comment: str | None = None, *, delete_file: bool = False) -> AgendaItem:
    return _task_operations(ctx).delete_task(task_name, closing_comment, delete_file=delete_file)


def rename_task(ctx: ElroyContext, old_name: str, new_name: str) -> AgendaItem:
    return _task_operations(ctx).rename_task(old_name, new_name)


def update_task_text(ctx: ElroyContext, task_name: str, new_text: str) -> AgendaItem:
    return _task_operations(ctx).update_task_text(task_name, new_text)


def task_path(task: AgendaItem) -> Path:
    return TaskOperationService.task_path(task)


def get_task_body(task: AgendaItem) -> str:
    return TaskOperationService.get_task_body(task)


def get_task_metadata(task: AgendaItem) -> dict[str, Any]:
    return TaskOperationService.get_task_metadata(task)
