from datetime import date
from typing import Any, cast

from sqlmodel import col, select

from ...core.ctx import ElroyContext
from ...db.db_models import AgendaItem
from ...utils.clock import ensure_utc, utc_now


def get_task_by_name(ctx: ElroyContext, name: str) -> AgendaItem | None:
    return ctx.db.exec(
        select(AgendaItem).where(
            AgendaItem.user_id == ctx.user_id,
            AgendaItem.name == name,
            cast(Any, AgendaItem.is_active),
        )
    ).first()


def get_active_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    return list(
        ctx.db.exec(
            select(AgendaItem)
            .where(
                AgendaItem.user_id == ctx.user_id,
                cast(Any, AgendaItem.is_active),
            )
            .order_by(col(AgendaItem.created_at))
        ).all()
    )


def get_triggered_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    return [task for task in get_active_tasks(ctx) if task.trigger_datetime or task.trigger_context]


def get_due_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    now = utc_now()
    return [task for task in get_active_tasks(ctx) if task.trigger_datetime is not None and ensure_utc(task.trigger_datetime) <= now]


def get_today_tasks(ctx: ElroyContext) -> list[AgendaItem]:
    today = date.today().isoformat()
    return [task for task in get_active_tasks(ctx) if task.to_fact() and today in task.to_fact()]
