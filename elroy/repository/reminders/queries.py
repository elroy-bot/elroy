from rich.table import Table
from sqlmodel import col, select

from ...core.constants import allow_unused, user_only_tool
from ...core.ctx import ElroyConfig
from ...core.session import run_with_turn
from ...core.turn import TurnContext
from ...db.db_models import AgendaItem
from ...utils.clock import db_time_to_local
from ..context_messages.data_models import ContextMessage
from ..context_messages.tools import to_synthetic_tool_call
from ..tasks.queries import (
    do_get_due_tasks,
    do_get_task_by_name,
    do_get_triggered_tasks,
)
from ..user.session import build_user_session

DueItemLike = AgendaItem


def do_get_db_due_item_by_name(turn: TurnContext, name: str) -> DueItemLike | None:
    task = do_get_task_by_name(turn, name)
    if task and (task.trigger_datetime or task.trigger_context):
        return task
    return None


def do_get_active_due_items(turn: TurnContext) -> list[DueItemLike]:
    return list(do_get_triggered_tasks(turn))


def do_get_due_items(turn: TurnContext, include_completed: bool = False) -> list[DueItemLike]:
    if not include_completed:
        return do_get_active_due_items(turn)

    user_session = build_user_session(turn)
    return list(
        user_session.db.exec(
            select(AgendaItem).where(
                AgendaItem.user_id == user_session.user_id,
                col(AgendaItem.status).in_(["created", "completed"]),
                ((col(AgendaItem.trigger_datetime).is_not(None)) | (col(AgendaItem.trigger_context).is_not(None))),
            )
        ).all()
    )


def do_get_active_due_item_names(turn: TurnContext) -> list[str]:
    return [item.name for item in do_get_active_due_items(turn)]


def do_get_due_timed_items(turn: TurnContext) -> list[DueItemLike]:
    return list(do_get_due_tasks(turn))


def do_get_due_item_by_name(turn: TurnContext, item_name: str) -> str | None:
    due_item = do_get_db_due_item_by_name(turn, item_name)
    return due_item.text if due_item else None


def do_get_due_item_context_msgs(turn: TurnContext) -> list[ContextMessage]:
    due_items = do_get_due_timed_items(turn)
    if not due_items:
        return []

    lines: list[str] = []
    for due_item in due_items:
        trigger_dt = due_item.trigger_datetime
        if not trigger_dt:
            continue
        lines.append(
            f"⏰ DUE ITEM: '{due_item.name}' - {due_item.text}\n\nThis item was scheduled for {trigger_dt.strftime('%Y-%m-%d %H:%M:%S')} and is now due. Please inform the user about it and then use the delete_due_item tool to remove it from active due items."
        )
    return to_synthetic_tool_call("get_due_items", "\n".join(lines))


def get_db_due_item_by_name(ctx: ElroyConfig, name: str) -> DueItemLike | None:
    return run_with_turn(ctx, do_get_db_due_item_by_name, name)


def get_active_due_items(ctx: ElroyConfig) -> list[DueItemLike]:
    return run_with_turn(ctx, do_get_active_due_items)


def get_due_items(ctx: ElroyConfig, include_completed: bool = False) -> list[DueItemLike]:
    return run_with_turn(ctx, do_get_due_items, include_completed)


def get_active_due_item_names(ctx: ElroyConfig) -> list[str]:
    return run_with_turn(ctx, do_get_active_due_item_names)


def get_due_timed_items(ctx: ElroyConfig) -> list[DueItemLike]:
    return run_with_turn(ctx, do_get_due_timed_items)


@allow_unused
def get_due_item_by_name(ctx: ElroyConfig, item_name: str) -> str | None:
    return run_with_turn(ctx, do_get_due_item_by_name, item_name)


@user_only_tool
def print_active_due_items(ctx: ElroyConfig, n: int | None = None) -> str | Table:
    return _print_all_due_items(ctx, True, n)


@user_only_tool
def print_inactive_due_items(ctx: ElroyConfig, n: int | None = None) -> str | Table:
    return _print_all_due_items(ctx, False, n)


def _print_all_due_items(ctx: ElroyConfig, active: bool, n: int | None = None) -> Table | str:
    due_items = [item for item in get_due_items(ctx, include_completed=not active) if bool(item.is_active) == active]

    if not due_items:
        status = "active" if active else "inactive"
        return f"No {status} due items found."

    title = "Active Due Items" if active else "Inactive Due Items"
    table = Table(title=title, show_lines=True)
    table.add_column("Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Type", justify="left", style="yellow")
    table.add_column("Trigger Time", justify="left", style="green")
    table.add_column("Context", justify="left", style="green")
    table.add_column("Text", justify="left", style="green")
    table.add_column("Created At", justify="left", style="green")

    for due_item in list(due_items)[:n]:
        item_type = "Timed" if due_item.trigger_datetime else "Contextual"
        trigger_time = db_time_to_local(due_item.trigger_datetime).strftime("%Y-%m-%d %H:%M:%S") if due_item.trigger_datetime else "N/A"
        context = due_item.trigger_context or "N/A"
        table.add_row(
            due_item.name,
            item_type,
            trigger_time,
            context,
            due_item.text,
            db_time_to_local(due_item.created_at).strftime("%Y-%m-%d %H:%M:%S"),
        )
    return table


def get_due_item_context_msgs(ctx: ElroyConfig) -> list[ContextMessage]:
    return run_with_turn(ctx, do_get_due_item_context_msgs)
