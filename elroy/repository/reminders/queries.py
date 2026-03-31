from rich.table import Table
from sqlmodel import col, select

from ...core.constants import allow_unused, user_only_tool
from ...core.ctx import ElroyContext
from ...db.db_models import AgendaItem
from ...utils.clock import db_time_to_local
from ..context_messages.data_models import ContextMessage
from ..context_messages.tools import to_synthetic_tool_call
from ..tasks.queries import get_due_tasks, get_task_by_name, get_triggered_tasks

DueItemLike = AgendaItem


def get_db_due_item_by_name(ctx: ElroyContext, name: str) -> DueItemLike | None:
    task = get_task_by_name(ctx, name)
    if task and (task.trigger_datetime or task.trigger_context):
        return task
    return None


def get_active_due_items(ctx: ElroyContext) -> list[DueItemLike]:
    return list(get_triggered_tasks(ctx))


def get_due_items(ctx: ElroyContext, include_completed: bool = False) -> list[DueItemLike]:
    if not include_completed:
        return get_active_due_items(ctx)

    return list(
        ctx.db.exec(
            select(AgendaItem).where(
                AgendaItem.user_id == ctx.user_id,
                col(AgendaItem.status).in_(["created", "completed"]),
                ((col(AgendaItem.trigger_datetime).is_not(None)) | (col(AgendaItem.trigger_context).is_not(None))),
            )
        ).all()
    )


def get_active_due_item_names(ctx: ElroyContext) -> list[str]:
    return [item.name for item in get_active_due_items(ctx)]


def get_due_timed_items(ctx: ElroyContext) -> list[DueItemLike]:
    return list(get_due_tasks(ctx))


@allow_unused
def get_due_item_by_name(ctx: ElroyContext, item_name: str) -> str | None:
    due_item = get_db_due_item_by_name(ctx, item_name)
    return due_item.text if due_item else None


@user_only_tool
def print_active_due_items(ctx: ElroyContext, n: int | None = None) -> str | Table:
    return _print_all_due_items(ctx, True, n)


@user_only_tool
def print_inactive_due_items(ctx: ElroyContext, n: int | None = None) -> str | Table:
    return _print_all_due_items(ctx, False, n)


def _print_all_due_items(ctx: ElroyContext, active: bool, n: int | None = None) -> Table | str:
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
        context = due_item.trigger_context if due_item.trigger_context else "N/A"
        table.add_row(
            due_item.name,
            item_type,
            trigger_time,
            context,
            due_item.text,
            db_time_to_local(due_item.created_at).strftime("%Y-%m-%d %H:%M:%S"),
        )
    return table


def get_due_item_context_msgs(ctx: ElroyContext) -> list[ContextMessage]:
    due_items = get_due_timed_items(ctx)
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
