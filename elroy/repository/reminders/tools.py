from typing import Optional

from ...core.constants import SYSTEM, RecoverableToolError, tool
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...utils.clock import utc_now
from ..context_messages.data_models import ContextMessage
from ..context_messages.operations import add_context_message
from ..recall.operations import upsert_embedding_if_needed
from ..recall.transforms import to_recalled_memory_metadata
from .operations import create_reminder as create_reminder_op
from .operations import (
    deactivate_reminder,
)
from .queries import (
    get_active_reminder_names,
    get_db_reminder_by_name,
)

logger = get_logger()


@tool
def create_reminder(
    ctx: ElroyContext,
    name: str,
    text: str,
    trigger_time: Optional[str] = None,
    reminder_context: Optional[str] = None,
    is_recurring: bool = False,
) -> str:
    """Creates a reminder that can be triggered by time and/or context.

    Args:
        name (str): Name of the reminder (must be unique)
        text (str): The reminder message to display when triggered
        trigger_time (Optional[str]): When the reminder should trigger in format "YYYY-MM-DD HH:MM" (e.g., "2024-12-25 09:00"). If provided, creates a timed reminder.
        reminder_context (Optional[str]): Description of the context/situation when this reminder should be triggered (e.g., "when user mentions work stress", "when user asks about exercise"). If provided, creates a contextual reminder.
        is_recurring (bool): Whether this reminder should trigger multiple times (True) or just once (False). Only applies to contextual reminders. Default is False.

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
    reminder = create_reminder_op(ctx, name, text, trigger_time=trigger_time, reminder_context=reminder_context, is_recurring=is_recurring)

    # Generate appropriate confirmation message
    if trigger_time and reminder_context:
        recurring_text = " (recurring)" if is_recurring else ""
        return f"Hybrid reminder '{name}' has been created for {trigger_time} and context: {reminder_context}{recurring_text}."
    elif trigger_time:
        return f"Timed reminder '{name}' has been created for {trigger_time}."
    elif reminder_context:
        recurring_text = " (recurring)" if is_recurring else " (one-time)"
        return f"Contextual reminder '{name}' has been created{recurring_text}."
    else:
        # This should not happen due to validation in create_reminder_op, but just in case
        raise ValueError("Either trigger_time or reminder_context must be provided")


@tool
def delete_reminder(ctx: ElroyContext, name: str) -> str:
    """Permanently deletes a reminder (timed, contextual, or hybrid).

    Args:
        name (str): The name of the reminder to delete

    Returns:
        str: Confirmation message that the reminder was deleted

    Raises:
        ReminderDoesNotExistError: If the reminder doesn't exist
    """
    deactivate_reminder(ctx, name)
    return f"Reminder '{name}' has been deleted."


@tool
def rename_reminder(ctx: ElroyContext, old_name: str, new_name: str) -> str:
    """Renames an existing reminder.

    Args:
        old_name (str): The current name of the reminder
        new_name (str): The new name for the reminder

    Returns:
        str: A confirmation message that the reminder was renamed

    Raises:
        Exception: If the reminder with old_name doesn't exist or new_name already exists
    """
    # Check if the old reminder exists and is active
    old_reminder = get_db_reminder_by_name(ctx, old_name)

    if not old_reminder:
        active_names = get_active_reminder_names(ctx)
        raise Exception(f"Active reminder '{old_name}' not found for user {ctx.user_id}. Active reminders: " + ", ".join(active_names))

    existing_reminder_with_new_name = get_db_reminder_by_name(ctx, new_name)

    if existing_reminder_with_new_name:
        raise Exception(f"Active reminder '{new_name}' already exists for user {ctx.user_id}")

    # Rename the reminder
    old_reminder.name = new_name
    old_reminder.updated_at = utc_now()

    ctx.db.commit()
    ctx.db.refresh(old_reminder)

    upsert_embedding_if_needed(ctx, old_reminder)

    add_context_message(
        ctx,
        ContextMessage(
            role=SYSTEM,
            content=f"Reminder '{old_name}' has been renamed to '{new_name}'",
            memory_metadata=[to_recalled_memory_metadata(old_reminder)],
            chat_model=ctx.chat_model.name,
        ),
    )
    return f"Reminder '{old_name}' has been renamed to '{new_name}'."


@tool
def print_reminder(ctx: ElroyContext, name: str) -> str:
    """Prints the reminder with the given name.

    Args:
        name (str): Name of the reminder to retrieve

    Returns:
        str: The reminder's details if found, or an error message if not found
    """
    reminder = get_db_reminder_by_name(ctx, name)
    if reminder:
        details = [f"Reminder '{name}':"]

        if reminder.trigger_datetime:
            trigger_time = reminder.trigger_datetime.strftime("%Y-%m-%d %H:%M:%S")
            details.append(f"Trigger Time: {trigger_time}")

        if reminder.reminder_context:
            details.append(f"Context: {reminder.reminder_context}")
            recurring_text = "Yes" if reminder.is_recurring else "No"
            details.append(f"Recurring: {recurring_text}")

        details.append(f"Text: {reminder.text}")

        return "\n".join(details)
    else:
        valid_reminders = ",".join(sorted(get_active_reminder_names(ctx)))
        raise RecoverableToolError(f"Reminder '{name}' not found. Valid reminders: {valid_reminders}")


@tool
def update_reminder_text(ctx: ElroyContext, name: str, new_text: str) -> str:
    """Updates the text of an existing reminder.

    Args:
        name (str): Name of the reminder to update
        new_text (str): The new reminder text

    Returns:
        str: Confirmation message that the reminder was updated

    Raises:
        RecoverableToolError: If the reminder doesn't exist
    """
    reminder = get_db_reminder_by_name(ctx, name)
    if not reminder:
        valid_reminders = ",".join(sorted(get_active_reminder_names(ctx)))
        raise RecoverableToolError(f"Reminder '{name}' not found. Valid reminders: {valid_reminders}")

    old_text = reminder.text
    reminder.text = new_text
    reminder.updated_at = utc_now()

    ctx.db.commit()
    ctx.db.refresh(reminder)

    upsert_embedding_if_needed(ctx, reminder)

    add_context_message(
        ctx,
        ContextMessage(
            role=SYSTEM,
            content=f"Updated reminder '{name}' text from '{old_text}' to '{new_text}'",
            memory_metadata=[to_recalled_memory_metadata(reminder)],
            chat_model=ctx.chat_model.name,
        ),
    )
    return f"Reminder '{name}' text has been updated."
