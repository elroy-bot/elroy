from typing import List, Optional, Union

from rich.table import Table
from sqlmodel import col, select

from ...core.constants import RecoverableToolError, allow_unused, user_only_tool
from ...core.ctx import ElroyContext
from ...db.db_models import Reminder
from ...utils.clock import db_time_to_local, utc_now


def get_db_reminder_by_name(ctx: ElroyContext, name: str) -> Optional[Reminder]:
    """Get any reminder (timed or contextual) by name"""
    return ctx.db.exec(
        select(Reminder).where(
            Reminder.user_id == ctx.user_id,
            Reminder.name == name,
            Reminder.is_active == True,
        )
    ).first()


def get_active_reminders(ctx: ElroyContext) -> List[Reminder]:
    """Get all active reminders"""
    return list(
        ctx.db.exec(
            select(Reminder)
            .where(
                Reminder.user_id == ctx.user_id,
                Reminder.is_active == True,
            )
            .order_by(col(Reminder.created_at))
        ).all()
    )


def get_active_reminder_names(ctx: ElroyContext) -> List[str]:
    """Gets the list of names for all active reminders"""
    return [reminder.name for reminder in get_active_reminders(ctx)]


def get_due_timed_reminders(ctx: ElroyContext) -> List[Reminder]:
    """Get timed reminders that are due (trigger_datetime <= now)

    Args:
        ctx (ElroyContext): The Elroy context.

    Returns:
        List[Reminder]: List of due timed reminders.
    """
    now = utc_now()
    return list(
        ctx.db.exec(
            select(Reminder).where(
                Reminder.user_id == ctx.user_id,
                Reminder.is_active == True,
                Reminder.trigger_datetime.is_not(None),
                Reminder.trigger_datetime <= now,
            )
        ).fetchall()
    )


@allow_unused
def get_reminder_by_name(ctx: ElroyContext, reminder_name: str) -> Optional[str]:
    """Get the text for a reminder by name

    Args:
        ctx (ElroyContext): context obj
        reminder_name (str): Name of the reminder

    Returns:
        Optional[str]: The text for the reminder with the given name
    """
    reminder = get_db_reminder_by_name(ctx, reminder_name)
    if reminder:
        return reminder.text
    else:
        raise RecoverableToolError(f"Reminder '{reminder_name}' not found")


@user_only_tool
def print_active_reminders(ctx: ElroyContext, n: Optional[int] = None) -> Union[str, Table]:
    """Prints the last n active reminders (both timed and contextual). If n is None, prints all active reminders.

    Args:
        n (Optional[int], optional): Number of reminders to print. Defaults to None.
    """
    return _print_all_reminders(ctx, True, n)


@user_only_tool
def print_inactive_reminders(ctx: ElroyContext, n: Optional[int] = None) -> Union[str, Table]:
    """Prints the last n inactive reminders (both timed and contextual). If n is None, prints all inactive reminders.

    Args:
        n (Optional[int], optional): Number of reminders to print. Defaults to None.
    """
    return _print_all_reminders(ctx, False, n)


def _print_all_reminders(ctx: ElroyContext, active: bool, n: Optional[int] = None) -> Union[Table, str]:
    """Prints the last n reminders (both timed and contextual). If n is None, prints all reminders.

    Args:
        ctx (ElroyContext): context obj
        active (bool): Whether to show active or inactive reminders
        n (Optional[int], optional): Number of reminders to print. Defaults to None.
    """
    reminders = ctx.db.exec(
        select(Reminder)
        .where(
            Reminder.user_id == ctx.user_id,
            Reminder.is_active == active,
        )
        .order_by(Reminder.created_at.desc())
    ).all()

    if not reminders:
        status = "active" if active else "inactive"
        return f"No {status} reminders found."

    title = "Active Reminders" if active else "Inactive Reminders"
    table = Table(title=title, show_lines=True)
    table.add_column("Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Type", justify="left", style="yellow")
    table.add_column("Trigger Time", justify="left", style="green")
    table.add_column("Context", justify="left", style="green")
    table.add_column("Text", justify="left", style="green")
    table.add_column("Created At", justify="left", style="green")

    for reminder in list(reminders)[:n]:
        reminder_type = "Timed" if reminder.trigger_datetime else "Contextual"
        trigger_time = db_time_to_local(reminder.trigger_datetime).strftime("%Y-%m-%d %H:%M:%S") if reminder.trigger_datetime else "N/A"
        context = reminder.reminder_context if reminder.reminder_context else "N/A"

        table.add_row(
            reminder.name,
            reminder_type,
            trigger_time,
            context,
            reminder.text,
            db_time_to_local(reminder.created_at).strftime("%Y-%m-%d %H:%M:%S"),
        )
    return table
