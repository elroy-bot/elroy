from typing import List, Optional, Union

from rich.table import Table
from sqlmodel import select

from ...core.constants import RecoverableToolError, allow_unused, user_only_tool
from ...core.ctx import ElroyContext
from ...db.db_models import ContextualReminder, TimedReminder
from ...utils.clock import db_time_to_local, utc_now


def get_active_timed_reminders(ctx: ElroyContext) -> List[TimedReminder]:
    """
    Retrieve active timed reminders for a given user.

    Args:
        ctx (ElroyContext): The Elroy context.

    Returns:
        List[TimedReminder]: A list of active timed reminders.
    """
    return list(get_timed_reminders(ctx, True))


def get_active_contextual_reminders(ctx: ElroyContext) -> List[ContextualReminder]:
    """
    Retrieve active contextual reminders for a given user.

    Args:
        ctx (ElroyContext): The Elroy context.

    Returns:
        List[ContextualReminder]: A list of active contextual reminders.
    """
    return list(get_contextual_reminders(ctx, True))


def get_timed_reminders(ctx: ElroyContext, active: bool):
    return ctx.db.exec(
        select(TimedReminder)
        .where(
            TimedReminder.user_id == ctx.user_id,
            TimedReminder.is_active == active,
        )
        .order_by(TimedReminder.trigger_datetime)  # type: ignore
    ).all()


def get_contextual_reminders(ctx: ElroyContext, active: bool):
    return ctx.db.exec(
        select(ContextualReminder)
        .where(
            ContextualReminder.user_id == ctx.user_id,
            ContextualReminder.is_active == active,
        )
        .order_by(ContextualReminder.created_at)  # type: ignore
    ).all()


def get_db_timed_reminder_by_name(ctx: ElroyContext, name: str) -> Optional[TimedReminder]:
    return ctx.db.exec(
        select(TimedReminder).where(
            TimedReminder.user_id == ctx.user_id,
            TimedReminder.name == name,
            TimedReminder.is_active == True,
        )
    ).first()


def get_db_contextual_reminder_by_name(ctx: ElroyContext, name: str) -> Optional[ContextualReminder]:
    return ctx.db.exec(
        select(ContextualReminder).where(
            ContextualReminder.user_id == ctx.user_id,
            ContextualReminder.name == name,
            ContextualReminder.is_active == True,
        )
    ).first()


def get_active_timed_reminder_names(ctx: ElroyContext) -> List[str]:
    """Gets the list of names for all active timed reminders

    Returns:
        List[str]: List of names for all active timed reminders
    """
    return [reminder.name for reminder in get_active_timed_reminders(ctx)]


def get_active_contextual_reminder_names(ctx: ElroyContext) -> List[str]:
    """Gets the list of names for all active contextual reminders

    Returns:
        List[str]: List of names for all active contextual reminders
    """
    return [reminder.name for reminder in get_active_contextual_reminders(ctx)]


def get_due_timed_reminders(ctx: ElroyContext) -> List[TimedReminder]:
    """Get timed reminders that are due (trigger_datetime <= now)

    Args:
        ctx (ElroyContext): The Elroy context.

    Returns:
        List[TimedReminder]: List of due timed reminders.
    """
    now = utc_now()
    return list(
        ctx.db.exec(
            select(TimedReminder).where(
                TimedReminder.user_id == ctx.user_id,
                TimedReminder.is_active == True,
                TimedReminder.trigger_datetime <= now,
            )
        ).fetchall()
    )


@allow_unused
def get_timed_reminder_by_name(ctx: ElroyContext, reminder_name: str) -> Optional[str]:
    """Get the text for a timed reminder by name

    Args:
        ctx (ElroyContext): context obj
        reminder_name (str): Name of the reminder

    Returns:
        Optional[str]: The text for the reminder with the given name
    """
    reminder = get_db_timed_reminder_by_name(ctx, reminder_name)
    if reminder:
        return reminder.text
    else:
        raise RecoverableToolError(f"Timed reminder '{reminder_name}' not found")


@allow_unused
def get_contextual_reminder_by_name(ctx: ElroyContext, reminder_name: str) -> Optional[str]:
    """Get the text for a contextual reminder by name

    Args:
        ctx (ElroyContext): context obj
        reminder_name (str): Name of the reminder

    Returns:
        Optional[str]: The text for the reminder with the given name
    """
    reminder = get_db_contextual_reminder_by_name(ctx, reminder_name)
    if reminder:
        return reminder.text
    else:
        raise RecoverableToolError(f"Contextual reminder '{reminder_name}' not found")


@user_only_tool
def print_active_timed_reminders(ctx: ElroyContext, n: Optional[int] = None) -> Union[str, Table]:
    """Prints the last n active timed reminders. If n is None, prints all active timed reminders.

    Args:
        n (Optional[int], optional): Number of reminders to print. Defaults to None.
    """
    return _print_timed_reminders(ctx, True, n)


@user_only_tool
def print_inactive_timed_reminders(ctx: ElroyContext, n: Optional[int] = None) -> Union[str, Table]:
    """Prints the last n inactive timed reminders. If n is None, prints all inactive timed reminders.

    Args:
        n (Optional[int], optional): Number of reminders to print. Defaults to None.
    """
    return _print_timed_reminders(ctx, False, n)


@user_only_tool
def print_active_contextual_reminders(ctx: ElroyContext, n: Optional[int] = None) -> Union[str, Table]:
    """Prints the last n active contextual reminders. If n is None, prints all active contextual reminders.

    Args:
        n (Optional[int], optional): Number of reminders to print. Defaults to None.
    """
    return _print_contextual_reminders(ctx, True, n)


@user_only_tool
def print_inactive_contextual_reminders(ctx: ElroyContext, n: Optional[int] = None) -> Union[str, Table]:
    """Prints the last n inactive contextual reminders. If n is None, prints all inactive contextual reminders.

    Args:
        n (Optional[int], optional): Number of reminders to print. Defaults to None.
    """
    return _print_contextual_reminders(ctx, False, n)


def _print_timed_reminders(ctx: ElroyContext, active: bool, n: Optional[int] = None) -> Union[Table, str]:
    """Prints the last n timed reminders. If n is None, prints all timed reminders.

    Args:
        ctx (ElroyContext): context obj
        active (bool): Whether to show active or inactive reminders
        n (Optional[int], optional): Number of reminders to print. Defaults to None.
    """
    reminders = sorted(get_timed_reminders(ctx, active), key=lambda r: r.trigger_datetime, reverse=True)

    if not reminders:
        status = "active" if active else "inactive"
        return f"No {status} timed reminders found."

    title = "Active Timed Reminders" if active else "Inactive Timed Reminders"
    table = Table(title=title, show_lines=True)
    table.add_column("Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Trigger Time", justify="left", style="green")
    table.add_column("Text", justify="left", style="green")
    table.add_column("Created At", justify="left", style="green")

    for reminder in reminders[:n]:
        table.add_row(
            reminder.name,
            db_time_to_local(reminder.trigger_datetime).strftime("%Y-%m-%d %H:%M:%S") if reminder.trigger_datetime else "Not set",
            reminder.text,
            db_time_to_local(reminder.created_at).strftime("%Y-%m-%d %H:%M:%S"),
        )
    return table


def _print_contextual_reminders(ctx: ElroyContext, active: bool, n: Optional[int] = None) -> Union[Table, str]:
    """Prints the last n contextual reminders. If n is None, prints all contextual reminders.

    Args:
        ctx (ElroyContext): context obj
        active (bool): Whether to show active or inactive reminders
        n (Optional[int], optional): Number of reminders to print. Defaults to None.
    """
    reminders = sorted(get_contextual_reminders(ctx, active), key=lambda r: r.created_at, reverse=True)

    if not reminders:
        status = "active" if active else "inactive"
        return f"No {status} contextual reminders found."

    title = "Active Contextual Reminders" if active else "Inactive Contextual Reminders"
    table = Table(title=title, show_lines=True)
    table.add_column("Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Context", justify="left", style="green")
    table.add_column("Text", justify="left", style="green")
    table.add_column("Recurring", justify="left", style="green")
    table.add_column("Created At", justify="left", style="green")

    for reminder in reminders[:n]:
        table.add_row(
            reminder.name,
            reminder.reminder_context,
            reminder.text,
            "Yes" if reminder.is_recurring else "No",
            db_time_to_local(reminder.created_at).strftime("%Y-%m-%d %H:%M:%S"),
        )
    return table
