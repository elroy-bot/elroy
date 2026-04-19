from datetime import datetime

from ...core.ctx import ElroyContext
from .reminder_orchestrator import ReminderOrchestrator


def _orchestrator(ctx: ElroyContext) -> ReminderOrchestrator:
    from ..tasks.operations import complete_task, create_task, delete_task

    return ReminderOrchestrator(
        ctx=ctx,
        create_task_fn=lambda name, text, **kwargs: create_task(ctx, name, text, **kwargs),
        complete_task_fn=lambda item_name, closing_comment: complete_task(ctx, item_name, closing_comment),
        delete_task_fn=lambda item_name, closing_comment: delete_task(ctx, item_name, closing_comment),
    )


def create_onboarding_due_item(ctx: ElroyContext, preferred_name: str) -> None:
    _orchestrator(ctx).create_onboarding_due_item(preferred_name)


def do_create_due_item(
    ctx: ElroyContext,
    name: str,
    text: str,
    trigger_time: datetime | None = None,
    trigger_context: str | None = None,
):
    return _orchestrator(ctx).do_create_due_item(name, text, trigger_time, trigger_context)


def do_complete_due_item(ctx: ElroyContext, item_name: str, closing_comment: str | None = None) -> str:
    return _orchestrator(ctx).do_complete_due_item(item_name, closing_comment)


def do_delete_due_item(ctx: ElroyContext, item_name: str, closing_comment: str | None = None) -> str:
    return _orchestrator(ctx).do_delete_due_item(item_name, closing_comment)
