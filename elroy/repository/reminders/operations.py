from ...core.constants import RecoverableToolError
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
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


def deactivate_reminder(ctx: ElroyContext, reminder_name: str) -> None:
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
