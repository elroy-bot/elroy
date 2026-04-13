from ...core.ctx import ElroyContext
from ...core.services.task_service import TaskQueryService
from ...db.db_models import AgendaItem


def _task_queries(ctx: ElroyContext) -> TaskQueryService:
    return TaskQueryService(ctx.db, ctx.user_id)


def get_task_by_name(ctx: ElroyContext, name: str) -> AgendaItem | None:
    return _task_queries(ctx).get_task_by_name(name)


def get_active_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    return _task_queries(ctx).get_active_tasks()


def get_triggered_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    return _task_queries(ctx).get_triggered_tasks()


def get_due_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    return _task_queries(ctx).get_due_tasks()


def get_today_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    return _task_queries(ctx).get_today_tasks()
