from datetime import datetime
from typing import Any, cast

from sqlmodel import select

from ...core.constants import RecoverableToolError
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import Reminder
from ...utils.clock import utc_now
from ...utils.utils import is_blank
from ..recall.operations import remove_from_context, upsert_embedding_if_needed
from .queries import get_active_reminder_names, get_db_reminder_by_name

logger = get_logger()


class ReminderAlreadyExistsError(RecoverableToolError):
    def __init__(self, reminder_name: str, reminder_type: str):
        super().__init__(f"{reminder_type} reminder '{reminder_name}' already exists")


def create_onboarding_reminder(ctx: ElroyContext, preferred_name: str) -> None:
    do_create_reminder(
        ctx=ctx,
        name=f"Introduce myself to {preferred_name}",
        text="Introduce myself - a few things that make me unique are my ability to form long term memories, and the ability to set and create reminders",
        reminder_context="When user logs in for the first time",
    )


def do_create_reminder(
    ctx: ElroyContext,
    name: str,
    text: str,
    trigger_time: datetime | None = None,
    reminder_context: str | None = None,
) -> Reminder:
    """Creates a reminder that can be triggered by time and/or context.

    Note: Either trigger_time or reminder_context should be set!

    Args:
        name (str): Name of the reminder (must be unique, should be human readable)
        text (str): The reminder message to display when triggered
        trigger_time (Optional[str]): When the reminder should trigger in format "YYYY-MM-DD HH:MM" (e.g., "2024-12-25 09:00"). If provided, creates a timed reminder.
        reminder_context (Optional[str]): Description of the context/situation when this reminder should be triggered (e.g., "when user mentions work stress", "when user asks about exercise"). If provided, creates a contextual reminder.

    Returns:
        str: A confirmation message that the reminder was created.

    Raises:
        ValueError: If name is empty or if neither trigger_time nor reminder_context is provided
        ReminderAlreadyExistsError: If a reminder with the same name already exists

    Note:
        - You can provide trigger_time only (timed reminder)
        - You can provide reminder_context only (contextual reminder)
        - You can provide both trigger_time and reminder_context (hybrid reminder that triggers on both conditions)
        - You must provide at least one of trigger_time or reminder_context
    """
    # Validation
    if is_blank(name):
        raise ValueError("Reminder name cannot be empty")

    if not trigger_time and not reminder_context:
        raise RecoverableToolError("Either trigger_time or reminder_context must be provided for reminders")

    if trigger_time and trigger_time < utc_now():
        raise RecoverableToolError(
            f"Attempted to create reminder for {trigger_time}, which is in the past. The current time is {utc_now()}"
        )

    # Check for existing reminder with same name
    existing_reminder = ctx.db.exec(
        select(Reminder).where(
            Reminder.user_id == ctx.user_id,
            Reminder.name == name,
            cast(Any, Reminder.is_active),
        )
    ).one_or_none()

    if existing_reminder:
        reminder_type = "Timed" if trigger_time else "Contextual"
        raise ReminderAlreadyExistsError(name, reminder_type)

    # Create the reminder
    reminder = ctx.db.persist(
        Reminder(
            user_id=ctx.user_id,
            name=name,
            text=text,
            trigger_datetime=trigger_time,
            reminder_context=reminder_context,
            status="created",
        )
    )

    upsert_embedding_if_needed(ctx, reminder)

    return reminder


def do_complete_reminder(ctx: ElroyContext, reminder_name: str, closing_comment: str | None = None) -> str:
    """Mark a reminder as completed

    Args:
        ctx (ElroyContext): The Elroy context
        reminder_name (str): Name of the reminder to complete
        closing_comment (Optional[str]): Optional comment on completion

    Returns:
        str: Confirmation message

    Raises:
        RecoverableToolError: If the reminder doesn't exist
    """
    reminder = get_db_reminder_by_name(ctx, reminder_name)

    if not reminder:
        active_names = get_active_reminder_names(ctx)
        raise RecoverableToolError(f"Active reminder '{reminder_name}' not found. Active reminders: {', '.join(active_names)}")

    if reminder.status == "completed":
        return f"Reminder '{reminder_name}' is already completed."

    logger.info(f"Completing reminder {reminder_name} for user {ctx.user_id}")

    reminder.status = "completed"
    reminder.is_active = False
    reminder.closing_comment = closing_comment
    reminder.updated_at = utc_now()  # noqa F841

    reminder = ctx.db.persist(reminder)
    upsert_embedding_if_needed(ctx, reminder)

    if closing_comment:
        return f"Reminder '{reminder_name}' has been marked as completed. Comment: {closing_comment}"
    else:
        return f"Reminder '{reminder_name}' has been marked as completed."


def do_delete_reminder(ctx: ElroyContext, reminder_name: str, closing_comment: str | None = None) -> str:
    """Delete a reminder (mark as deleted)

    Args:
        ctx (ElroyContext): The Elroy context
        reminder_name (str): Name of the reminder to delete
        closing_comment (Optional[str]): Optional comment on deletion

    Returns:
        str: Confirmation message

    Raises:
        RecoverableToolError: If the reminder doesn't exist
    """
    reminder = get_db_reminder_by_name(ctx, reminder_name)

    if not reminder:
        active_names = get_active_reminder_names(ctx)
        raise RecoverableToolError(f"Active reminder '{reminder_name}' not found. Active reminders: {', '.join(active_names)}")

    logger.info(f"Deleting reminder {reminder_name} for user {ctx.user_id}")

    reminder.status = "deleted"
    reminder.is_active = None
    reminder.closing_comment = closing_comment
    reminder.updated_at = utc_now()  # noqa F841

    remove_from_context(ctx, reminder)
    reminder = ctx.db.persist(reminder)
    upsert_embedding_if_needed(ctx, reminder)

    if closing_comment:
        return f"Reminder '{reminder_name}' has been deleted. Comment: {closing_comment}"
    else:
        return f"Reminder '{reminder_name}' has been deleted."
