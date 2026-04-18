from ...core.ctx import ElroyContext
from ..tasks.operations import TaskStore
from .operations import ReminderOrchestrator


def build_reminder_orchestrator(ctx: ElroyContext) -> ReminderOrchestrator:
    task_store = TaskStore(ctx.db, ctx.user_id)
    return ReminderOrchestrator(
        ctx=ctx,
        create_task_fn=task_store.create_task,
        complete_task_fn=task_store.complete_task,
        delete_task_fn=task_store.delete_task,
    )
