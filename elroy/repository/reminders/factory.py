from ...core.ctx import ElroyContext
from ..tasks.factory import build_task_mutation_orchestrator
from .operations import ReminderOrchestrator


def build_reminder_orchestrator(ctx: ElroyContext) -> ReminderOrchestrator:
    task_orchestrator = build_task_mutation_orchestrator(ctx)
    return ReminderOrchestrator(
        ctx=ctx,
        create_task_fn=task_orchestrator.create_task,
        complete_task_fn=task_orchestrator.complete_task,
        delete_task_fn=task_orchestrator.delete_task,
    )
