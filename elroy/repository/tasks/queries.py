from datetime import date

from ...core.ctx import ElroyContext
from ...db.db_models import AgendaItem
from ...utils.clock import ensure_utc, utc_now
from .factory import build_task_store


def get_task_by_name(ctx: ElroyContext, name: str) -> AgendaItem | None:
    return build_task_store(ctx).get_task_by_name(name)


def get_active_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    return build_task_store(ctx).get_active_tasks()


def get_triggered_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    return [task for task in get_active_tasks(ctx) if task.trigger_datetime or task.trigger_context]


def get_due_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    now = utc_now()
    return [task for task in get_active_tasks(ctx) if task.trigger_datetime is not None and ensure_utc(task.trigger_datetime) <= now]


def get_today_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    today = date.today().isoformat()
    return [task for task in get_active_tasks(ctx) if task.to_fact() and today in task.to_fact()]
