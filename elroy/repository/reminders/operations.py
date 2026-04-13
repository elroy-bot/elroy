from ...core.ctx import ElroyContext
from ...core.services.reminder_service import ReminderOperationService
from ...core.services.task_service import TaskOperationService
from ..recall.operations import remove_from_context, upsert_embedding_if_needed


def _task_operations(ctx: ElroyContext) -> TaskOperationService:
    return TaskOperationService(
        ctx.db,
        ctx.user_id,
        sync_embedding=lambda row: upsert_embedding_if_needed(ctx, row),
        remove_from_context=lambda row: remove_from_context(ctx, row),
    )


def _reminder_operations(ctx: ElroyContext) -> ReminderOperationService:
    return ReminderOperationService(
        ctx.db,
        ctx.user_id,
        task_operations=_task_operations(ctx),
    )


def create_onboarding_due_item(ctx: ElroyContext, preferred_name: str) -> None:
    _reminder_operations(ctx).create_onboarding_due_item(preferred_name)


def do_create_due_item(
    ctx: ElroyContext,
    name: str,
    text: str,
    trigger_time=None,
    trigger_context=None,
):
    return _reminder_operations(ctx).create_due_item(
        name=name,
        text=text,
        trigger_time=trigger_time,
        trigger_context=trigger_context,
    )


def do_complete_due_item(ctx: ElroyContext, item_name: str, closing_comment: str | None = None) -> str:
    return _reminder_operations(ctx).complete_due_item(item_name, closing_comment)


def do_delete_due_item(ctx: ElroyContext, item_name: str, closing_comment: str | None = None) -> str:
    return _reminder_operations(ctx).delete_due_item(item_name, closing_comment)
