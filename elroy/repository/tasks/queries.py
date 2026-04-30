from datetime import date

from ...core.ctx import ElroyConfig
from ...core.session import run_with_turn
from ...core.turn import TurnContext
from ...db.db_models import AgendaItem
from ...utils.clock import ensure_utc, utc_now
from .factory import build_task_store


def do_get_task_by_name(turn: TurnContext, name: str) -> AgendaItem | None:
    return build_task_store(turn).get_task_by_name(name)


def do_get_active_tasks(turn: TurnContext) -> list[AgendaItem]:
    return build_task_store(turn).get_active_tasks()


def do_get_triggered_tasks(turn: TurnContext) -> list[AgendaItem]:
    return [task for task in do_get_active_tasks(turn) if task.trigger_datetime or task.trigger_context]


def do_get_due_tasks(turn: TurnContext) -> list[AgendaItem]:
    now = utc_now()
    return [task for task in do_get_active_tasks(turn) if task.trigger_datetime is not None and ensure_utc(task.trigger_datetime) <= now]


def do_get_today_tasks(turn: TurnContext) -> list[AgendaItem]:
    today = date.today().isoformat()
    return [task for task in do_get_active_tasks(turn) if task.to_fact() and today in task.to_fact()]


def get_task_by_name(ctx: ElroyConfig, name: str) -> AgendaItem | None:
    return run_with_turn(ctx, do_get_task_by_name, name)


def get_active_tasks(ctx: ElroyConfig) -> list[AgendaItem]:
    return run_with_turn(ctx, do_get_active_tasks)


def get_triggered_tasks(ctx: ElroyConfig) -> list[AgendaItem]:
    return run_with_turn(ctx, do_get_triggered_tasks)


def get_due_tasks(ctx: ElroyConfig) -> list[AgendaItem]:
    return run_with_turn(ctx, do_get_due_tasks)


def get_today_tasks(ctx: ElroyConfig) -> list[AgendaItem]:
    return run_with_turn(ctx, do_get_today_tasks)
