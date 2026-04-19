from datetime import date, datetime

from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import AgendaItem
from .store import (
    TaskAlreadyExistsError as _TaskAlreadyExistsError,
)
from .store import (
    TaskStore,
)
from .store import (
    get_task_body as _get_task_body,
)
from .store import (
    get_task_metadata as _get_task_metadata,
)
from .store import (
    task_path as _task_path,
)

logger = get_logger()

TaskAlreadyExistsError = _TaskAlreadyExistsError


def _store(ctx: ElroyContext) -> TaskStore:
    return TaskStore(
        db=ctx.db,
        user_id=ctx.user_id,
    )


def _reindex_task(ctx: ElroyContext, task: AgendaItem) -> AgendaItem:
    from ..recall.operations import upsert_embedding_if_needed

    upsert_embedding_if_needed(ctx, task)
    return task


def _remove_task_from_context(ctx: ElroyContext, task: AgendaItem) -> None:
    from ..recall.operations import remove_from_context, upsert_embedding_if_needed

    remove_from_context(ctx, task)
    upsert_embedding_if_needed(ctx, task)


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
    return _reindex_task(
        ctx,
        _store(ctx).create_task(
            name,
            text,
            item_date=item_date,
            trigger_datetime=trigger_datetime,
            trigger_context=trigger_context,
            allow_past_trigger=allow_past_trigger,
        ),
    )


def complete_task(ctx: ElroyContext, task_name: str, closing_comment: str | None = None) -> AgendaItem:
    return _reindex_task(ctx, _store(ctx).complete_task(task_name, closing_comment))


def delete_task(ctx: ElroyContext, task_name: str, closing_comment: str | None = None, *, delete_file: bool = False) -> AgendaItem:
    task = _store(ctx).delete_task(task_name, closing_comment, delete_file=delete_file)
    _remove_task_from_context(ctx, task)
    return task


def rename_task(ctx: ElroyContext, old_name: str, new_name: str) -> AgendaItem:
    return _reindex_task(ctx, _store(ctx).rename_task(old_name, new_name))


def update_task_text(ctx: ElroyContext, task_name: str, new_text: str) -> AgendaItem:
    return _reindex_task(ctx, _store(ctx).update_task_text(task_name, new_text))


def task_path(task: AgendaItem):
    return _task_path(task)


def get_task_body(task: AgendaItem) -> str:
    return _get_task_body(task)


def get_task_metadata(task: AgendaItem) -> dict:
    return _get_task_metadata(task)
