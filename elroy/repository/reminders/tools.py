from sqlmodel import select
from toolz import pipe
from toolz.curried import filter

from ...core.constants import SYSTEM, RecoverableToolError, tool
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import Reminder
from ...utils.clock import utc_now
from ...utils.utils import first_or_none
from ..context_messages.data_models import ContextMessage
from ..context_messages.operations import add_context_message
from ..recall.operations import upsert_embedding_if_needed
from ..recall.transforms import to_recalled_memory_metadata
from .operations import (
    create_reminder,
    deactivate_reminder,
)
from .queries import (
    get_active_reminders,
    get_active_reminder_names,
    get_db_reminder_by_name,
)

logger = get_logger()


@tool
def create_timed_reminder(
    ctx: ElroyContext,
    name: str,
    text: str,
    trigger_time: str,
) -> str:
    """Creates a timed reminder that will trigger at a specific date and time.

    Args:
        name (str): Name of the reminder (must be unique)
        text (str): The reminder message to display when triggered
        trigger_time (str): When the reminder should trigger in format "YYYY-MM-DD HH:MM" (e.g., "2024-12-25 09:00")

    Returns:
        str: A confirmation message that the reminder was created.

    Raises:
        ValueError: If name is empty or trigger_time format is invalid
        ReminderAlreadyExistsError: If a timed reminder with the same name already exists
    """
    create_reminder(ctx, name, text, trigger_time=trigger_time)
    return f"Timed reminder '{name}' has been created for {trigger_time}."


@tool
def create_contextual_reminder(
    ctx: ElroyContext,
    name: str,
    text: str,
    reminder_context: str,
    is_recurring: bool = False,
) -> str:
    """Creates a contextual reminder that will trigger when certain conditions or contexts arise.

    Args:
        name (str): Name of the reminder (must be unique)
        text (str): The reminder message to display when triggered
        reminder_context (str): Description of the context/situation when this reminder should be triggered (e.g., "when user mentions work stress", "when user asks about exercise")
        is_recurring (bool): Whether this reminder should trigger multiple times (True) or just once (False). Default is False.

    Returns:
        str: A confirmation message that the reminder was created.

    Raises:
        ValueError: If name is empty
        ReminderAlreadyExistsError: If a contextual reminder with the same name already exists
    """
    create_reminder(ctx, name, text, reminder_context=reminder_context, is_recurring=is_recurring)
    recurring_text = " (recurring)" if is_recurring else " (one-time)"
    return f"Contextual reminder '{name}' has been created{recurring_text}."


@tool
def delete_timed_reminder(ctx: ElroyContext, name: str) -> str:
    """Permanently deletes a timed reminder.

    Args:
        name (str): The name of the timed reminder to delete

    Returns:
        str: Confirmation message that the reminder was deleted

    Raises:
        ReminderDoesNotExistError: If the reminder doesn't exist
    """
    deactivate_reminder(ctx, name)
    return f"Timed reminder '{name}' has been deleted."


@tool
def delete_contextual_reminder(ctx: ElroyContext, name: str) -> str:
    """Permanently deletes a contextual reminder.

    Args:
        name (str): The name of the contextual reminder to delete

    Returns:
        str: Confirmation message that the reminder was deleted

    Raises:
        ReminderDoesNotExistError: If the reminder doesn't exist
    """
    deactivate_reminder(ctx, name)
    return f"Contextual reminder '{name}' has been deleted."


@tool
def rename_timed_reminder(ctx: ElroyContext, old_name: str, new_name: str) -> str:
    """Renames an existing timed reminder.

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
    if old_reminder and not old_reminder.trigger_datetime:
        old_reminder = None  # Not a timed reminder

    if not old_reminder:
        active_names = get_active_reminder_names(ctx)
        raise Exception(
            f"Active timed reminder '{old_name}' not found for user {ctx.user_id}. Active reminders: "
            + ", ".join(active_names)
        )

    existing_reminder_with_new_name = get_db_reminder_by_name(ctx, new_name)

    if existing_reminder_with_new_name:
        raise Exception(f"Active timed reminder '{new_name}' already exists for user {ctx.user_id}")

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
            content=f"Timed reminder '{old_name}' has been renamed to '{new_name}'",
            memory_metadata=[to_recalled_memory_metadata(old_reminder)],
            chat_model=ctx.chat_model.name,
        ),
    )
    return f"Timed reminder '{old_name}' has been renamed to '{new_name}'."


@tool
def rename_contextual_reminder(ctx: ElroyContext, old_name: str, new_name: str) -> str:
    """Renames an existing contextual reminder.

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
    if old_reminder and not old_reminder.reminder_context:
        old_reminder = None  # Not a contextual reminder

    if not old_reminder:
        active_names = get_active_reminder_names(ctx)
        raise Exception(
            f"Active contextual reminder '{old_name}' not found for user {ctx.user_id}. Active reminders: "
            + ", ".join(active_names)
        )

    existing_reminder_with_new_name = get_db_reminder_by_name(ctx, new_name)

    if existing_reminder_with_new_name:
        raise Exception(f"Active contextual reminder '{new_name}' already exists for user {ctx.user_id}")

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
            content=f"Contextual reminder '{old_name}' has been renamed to '{new_name}'",
            memory_metadata=[to_recalled_memory_metadata(old_reminder)],
            chat_model=ctx.chat_model.name,
        ),
    )
    return f"Contextual reminder '{old_name}' has been renamed to '{new_name}'."


@tool
def print_timed_reminder(ctx: ElroyContext, name: str) -> str:
    """Prints the timed reminder with the given name.

    Args:
        name (str): Name of the reminder to retrieve

    Returns:
        str: The reminder's details if found, or an error message if not found
    """
    reminder = get_db_reminder_by_name(ctx, name)
    if reminder and reminder.trigger_datetime:
        trigger_time = reminder.trigger_datetime.strftime("%Y-%m-%d %H:%M:%S") if reminder.trigger_datetime else "Not set"
        return f"Timed Reminder '{name}':\nTrigger Time: {trigger_time}\nText: {reminder.text}"
    else:
        # Filter for timed reminders only
        timed_reminders = [r for r in get_active_reminders(ctx) if r.trigger_datetime]
        valid_reminders = ",".join(sorted([r.name for r in timed_reminders]))
        raise RecoverableToolError(f"Timed reminder '{name}' not found. Valid reminders: {valid_reminders}")


@tool
def print_contextual_reminder(ctx: ElroyContext, name: str) -> str:
    """Prints the contextual reminder with the given name.

    Args:
        name (str): Name of the reminder to retrieve

    Returns:
        str: The reminder's details if found, or an error message if not found
    """
    reminder = get_db_reminder_by_name(ctx, name)
    if reminder and reminder.reminder_context:
        recurring_text = "Yes" if reminder.is_recurring else "No"
        return f"Contextual Reminder '{name}':\nContext: {reminder.reminder_context}\nText: {reminder.text}\nRecurring: {recurring_text}"
    else:
        # Filter for contextual reminders only
        contextual_reminders = [r for r in get_active_reminders(ctx) if r.reminder_context]
        valid_reminders = ",".join(sorted([r.name for r in contextual_reminders]))
        raise RecoverableToolError(f"Contextual reminder '{name}' not found. Valid reminders: {valid_reminders}")


@tool
def update_timed_reminder_text(ctx: ElroyContext, name: str, new_text: str) -> str:
    """Updates the text of an existing timed reminder.

    Args:
        name (str): Name of the reminder to update
        new_text (str): The new reminder text

    Returns:
        str: Confirmation message that the reminder was updated

    Raises:
        RecoverableToolError: If the reminder doesn't exist
    """
    reminder = get_db_reminder_by_name(ctx, name)
    if not reminder or not reminder.trigger_datetime:
        # Filter for timed reminders only
        timed_reminders = [r for r in get_active_reminders(ctx) if r.trigger_datetime]
        valid_reminders = ",".join(sorted([r.name for r in timed_reminders]))
        raise RecoverableToolError(f"Timed reminder '{name}' not found. Valid reminders: {valid_reminders}")

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
            content=f"Updated timed reminder '{name}' text from '{old_text}' to '{new_text}'",
            memory_metadata=[to_recalled_memory_metadata(reminder)],
            chat_model=ctx.chat_model.name,
        ),
    )
    return f"Timed reminder '{name}' text has been updated."


@tool
def update_contextual_reminder_text(ctx: ElroyContext, name: str, new_text: str) -> str:
    """Updates the text of an existing contextual reminder.

    Args:
        name (str): Name of the reminder to update
        new_text (str): The new reminder text

    Returns:
        str: Confirmation message that the reminder was updated

    Raises:
        RecoverableToolError: If the reminder doesn't exist
    """
    reminder = get_db_reminder_by_name(ctx, name)
    if not reminder or not reminder.reminder_context:
        # Filter for contextual reminders only
        contextual_reminders = [r for r in get_active_reminders(ctx) if r.reminder_context]
        valid_reminders = ",".join(sorted([r.name for r in contextual_reminders]))
        raise RecoverableToolError(f"Contextual reminder '{name}' not found. Valid reminders: {valid_reminders}")

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
            content=f"Updated contextual reminder '{name}' text from '{old_text}' to '{new_text}'",
            memory_metadata=[to_recalled_memory_metadata(reminder)],
            chat_model=ctx.chat_model.name,
        ),
    )
    return f"Contextual reminder '{name}' text has been updated."
