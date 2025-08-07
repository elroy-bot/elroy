from datetime import datetime
from typing import Optional

from sqlmodel import select

from ...core.constants import RecoverableToolError
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import Reminder
from ...utils.utils import is_blank
from ..recall.operations import (
    remove_from_context,
    upsert_embedding_if_needed,
)
from .queries import get_active_reminders, get_db_reminder_by_name

logger = get_logger()


class ReminderAlreadyExistsError(RecoverableToolError):
    def __init__(self, reminder_name: str, reminder_type: str):
        super().__init__(f"{reminder_type} reminder '{reminder_name}' already exists")


class ReminderDoesNotExistError(RecoverableToolError):
    def __init__(self, reminder_name: str, reminder_type: str, available_names: list):
        super().__init__(f"{reminder_type} reminder '{reminder_name}' not found. Available: {', '.join(available_names)}")


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
    trigger_time: Optional[datetime] = None,
    reminder_context: Optional[str] = None,
) -> Reminder:
    """Creates a reminder that can be triggered by time and/or context.

    Args:
        name (str): Name of the reminder (must be unique)
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
        raise ValueError("Either trigger_time or reminder_context must be provided")

    # Check for existing reminder with same name
    existing_reminder = ctx.db.exec(
        select(Reminder).where(
            Reminder.user_id == ctx.user_id,
            Reminder.name == name,
            Reminder.is_active == True,
        )
    ).one_or_none()

    if existing_reminder:
        reminder_type = "Timed" if trigger_time else "Contextual"
        raise ReminderAlreadyExistsError(name, reminder_type)

    # Create the reminder
    reminder = Reminder(
        user_id=ctx.user_id,
        name=name,
        text=text,
        trigger_datetime=trigger_time,
        reminder_context=reminder_context,
    )  # type: ignore

    ctx.db.add(reminder)
    ctx.db.commit()
    ctx.db.refresh(reminder)

    upsert_embedding_if_needed(ctx, reminder)

    return reminder


def do_deactivate_reminder(ctx: ElroyContext, reminder_name: str) -> None:
    """Deactivate a reminder

    Args:
        ctx (ElroyContext): The Elroy context
        reminder_name (str): Name of the reminder to deactivate

    Raises:
        ReminderDoesNotExistError: If the reminder doesn't exist
    """
    reminder = get_db_reminder_by_name(ctx, reminder_name)

    if not reminder:
        active_reminders = get_active_reminders(ctx)
        raise ReminderDoesNotExistError(reminder_name, "Reminder", [r.name for r in active_reminders])

    reminder_type = "Timed" if reminder.trigger_datetime else "Contextual"
    logger.info(f"Deactivating {reminder_type.lower()} reminder {reminder_name} for user {ctx.user_id}")

    reminder.is_active = None
    remove_from_context(ctx, reminder)

    ctx.db.commit()
    ctx.db.refresh(reminder)

    upsert_embedding_if_needed(ctx, reminder)
