from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel
from sqlmodel import select

from ...core.constants import SYSTEM, RecoverableToolError
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import ContextualReminder, TimedReminder
from ...llm.client import query_llm_with_response_format
from ...utils.clock import string_to_datetime, utc_now
from ...utils.utils import is_blank
from ..context_messages.data_models import ContextMessage
from ..context_messages.operations import add_context_message
from ..recall.operations import (
    remove_from_context,
    upsert_embedding_if_needed,
)
from ..recall.transforms import to_recalled_memory_metadata
from .queries import get_active_contextual_reminders, get_active_timed_reminders

logger = get_logger()


class ReminderAlreadyExistsError(RecoverableToolError):
    def __init__(self, reminder_name: str, reminder_type: str):
        super().__init__(f"{reminder_type} reminder '{reminder_name}' already exists")


class ReminderDoesNotExistError(RecoverableToolError):
    def __init__(self, reminder_name: str, reminder_type: str, available_names: list):
        super().__init__(f"{reminder_type} reminder '{reminder_name}' not found. Available: {', '.join(available_names)}")


def do_create_reminder(ctx: ElroyContext, name: str, description: str) -> Union[TimedReminder, ContextualReminder]:

    class CreateTimedReminderRequest(BaseModel):
        name: str  # description: short name for the reminder
        text: str  # content of the reminder
        trigger_time: str  # Time the reminder should be sent, in ISO 8601 format without timezone. Be as specific as is appropriate. Assume datetime is in user's time zone.

    class CreateContextualReminderRequest(BaseModel):
        name: str  # description: short name for the reminder
        text: str  # content of the reminder
        reminder_context: str  # A description of the situation in which the reminder should be sent.

    class CreateReminderRequest(BaseModel):
        timed_reminder_request: Optional[CreateTimedReminderRequest]
        contextual_reminder_request: Optional[CreateContextualReminderRequest]

    req = query_llm_with_response_format(
        ctx.chat_model,
        system="""Your task is to translate user text into API call params. The reminder should be either a timed reminder, which should be sent to the user at a specific time, or a contextual remidner, which should be sent to the user when a certain situation arises. Your response should contain ONE OF CreateTimedReminderRequest, or CreateContextualReminderRequest""",
        prompt=f"#{name}\n#{description}",
        response_format=CreateReminderRequest,
    )

    if req.timed_reminder_request:
        # parse time assuming ISO 8601 format
        reminder_time = string_to_datetime(req.timed_reminder_request.trigger_time)

        return do_create_timed_reminder(ctx, req.timed_reminder_request.name, req.timed_reminder_request.text, reminder_time)

    elif req.contextual_reminder_request:
        return do_create_contextual_reminder(
            ctx,
            req.contextual_reminder_request.name,
            req.contextual_reminder_request.text,
            req.contextual_reminder_request.reminder_context,
        )

    else:
        raise ValueError("Request must contain either a timed or contextual reminder")


def do_create_timed_reminder(
    ctx: ElroyContext,
    name: str,
    text: str,
    trigger_time: Union[str, datetime],
) -> TimedReminder:
    """Create a new timed reminder

    Args:
        ctx (ElroyContext): The Elroy context
        name (str): Name of the reminder
        text (str): The reminder text
        trigger_time (Union[str, datetime]): When the reminder should trigger (e.g., "2024-12-25 09:00" or datetime object)

    Returns:
        TimedReminder: The created reminder

    Raises:
        ValueError: If name is empty
        ReminderAlreadyExistsError: If a reminder with the same name already exists
    """
    if is_blank(name):
        raise ValueError("Reminder name cannot be empty")

    existing_reminder = ctx.db.exec(
        select(TimedReminder).where(
            TimedReminder.user_id == ctx.user_id,
            TimedReminder.name == name,
            TimedReminder.is_active == True,
        )
    ).one_or_none()

    if existing_reminder:
        raise ReminderAlreadyExistsError(name, "Timed")

    # Parse the trigger time
    if isinstance(trigger_time, datetime):
        trigger_datetime = trigger_time
    elif isinstance(trigger_time, str):
        trigger_datetime = string_to_datetime(trigger_time) if trigger_time else utc_now()
    else:
        trigger_datetime = utc_now()

    reminder = TimedReminder(
        user_id=ctx.user_id,
        name=name,
        text=text,
        trigger_datetime=trigger_datetime,
    )  # type: ignore

    ctx.db.add(reminder)
    ctx.db.commit()
    ctx.db.refresh(reminder)

    add_context_message(
        ctx,
        ContextMessage(
            role=SYSTEM,
            content=f"New timed reminder created: '{name}' at {trigger_datetime.strftime('%Y-%m-%d %H:%M:%S')}",
            memory_metadata=[to_recalled_memory_metadata(reminder)],
            chat_model=ctx.chat_model.name,
        ),
    )

    upsert_embedding_if_needed(ctx, reminder)
    return reminder


def do_create_contextual_reminder(
    ctx: ElroyContext,
    name: str,
    text: str,
    reminder_context: str,
    is_recurring: bool = False,
) -> ContextualReminder:
    """Create a new contextual reminder

    Args:
        ctx (ElroyContext): The Elroy context
        name (str): Name of the reminder
        text (str): The reminder text
        reminder_context (str): The context that should trigger this reminder
        is_recurring (bool): Whether this reminder should recur

    Returns:
        ContextualReminder: The created reminder

    Raises:
        ValueError: If name is empty
        ReminderAlreadyExistsError: If a reminder with the same name already exists
    """
    if is_blank(name):
        raise ValueError("Reminder name cannot be empty")

    existing_reminder = ctx.db.exec(
        select(ContextualReminder).where(
            ContextualReminder.user_id == ctx.user_id,
            ContextualReminder.name == name,
            ContextualReminder.is_active == True,
        )
    ).one_or_none()

    if existing_reminder:
        raise ReminderAlreadyExistsError(name, "Contextual")

    reminder = ContextualReminder(
        user_id=ctx.user_id,
        name=name,
        text=text,
        reminder_context=reminder_context,
        is_recurring=is_recurring,
    )  # type: ignore

    ctx.db.add(reminder)
    ctx.db.commit()
    ctx.db.refresh(reminder)

    add_context_message(
        ctx,
        ContextMessage(
            role=SYSTEM,
            content=f"New contextual reminder created: '{name}' triggered by context: {reminder_context}",
            memory_metadata=[to_recalled_memory_metadata(reminder)],
            chat_model=ctx.chat_model.name,
        ),
    )

    upsert_embedding_if_needed(ctx, reminder)
    return reminder


def deactivate_timed_reminder(ctx: ElroyContext, reminder_name: str) -> None:
    """Deactivate a timed reminder

    Args:
        ctx (ElroyContext): The Elroy context
        reminder_name (str): Name of the reminder to deactivate

    Raises:
        ReminderDoesNotExistError: If the reminder doesn't exist
    """
    reminder = ctx.db.exec(
        select(TimedReminder).where(
            TimedReminder.user_id == ctx.user_id,
            TimedReminder.name == reminder_name,
            TimedReminder.is_active == True,
        )
    ).first()

    if not reminder:
        active_reminders = get_active_timed_reminders(ctx)
        raise ReminderDoesNotExistError(reminder_name, "Timed", [r.name for r in active_reminders])

    logger.info(f"Deactivating timed reminder {reminder_name} for user {ctx.user_id}")

    reminder.is_active = False
    remove_from_context(ctx, reminder)

    ctx.db.commit()
    ctx.db.refresh(reminder)

    upsert_embedding_if_needed(ctx, reminder)


def deactivate_contextual_reminder(ctx: ElroyContext, reminder_name: str) -> None:
    """Deactivate a contextual reminder

    Args:
        ctx (ElroyContext): The Elroy context
        reminder_name (str): Name of the reminder to deactivate

    Raises:
        ReminderDoesNotExistError: If the reminder doesn't exist
    """
    reminder = ctx.db.exec(
        select(ContextualReminder).where(
            ContextualReminder.user_id == ctx.user_id,
            ContextualReminder.name == reminder_name,
            ContextualReminder.is_active == True,
        )
    ).first()

    if not reminder:
        active_reminders = get_active_contextual_reminders(ctx)
        raise ReminderDoesNotExistError(reminder_name, "Contextual", [r.name for r in active_reminders])

    logger.info(f"Deactivating contextual reminder {reminder_name} for user {ctx.user_id}")

    reminder.is_active = False
    remove_from_context(ctx, reminder)

    ctx.db.commit()
    ctx.db.refresh(reminder)

    upsert_embedding_if_needed(ctx, reminder)


def trigger_timed_reminder(ctx: ElroyContext, reminder: TimedReminder) -> str:
    """Trigger a timed reminder and optionally deactivate it

    Args:
        ctx (ElroyContext): The Elroy context
        reminder (TimedReminder): The reminder to trigger

    Returns:
        str: The reminder text that was triggered
    """
    logger.info(f"Triggering timed reminder '{reminder.name}' for user {ctx.user_id}")

    add_context_message(
        ctx,
        ContextMessage(
            role=SYSTEM,
            content=f"⏰ Reminder: {reminder.text}",
            memory_metadata=[to_recalled_memory_metadata(reminder)],
            chat_model=ctx.chat_model.name,
        ),
    )

    # Deactivate the reminder after triggering (timed reminders are typically one-time)
    reminder.is_active = False
    ctx.db.commit()
    ctx.db.refresh(reminder)

    return reminder.text


def trigger_contextual_reminder(ctx: ElroyContext, reminder: ContextualReminder) -> str:
    """Trigger a contextual reminder and optionally deactivate it if not recurring

    Args:
        ctx (ElroyContext): The Elroy context
        reminder (ContextualReminder): The reminder to trigger

    Returns:
        str: The reminder text that was triggered
    """
    logger.info(f"Triggering contextual reminder '{reminder.name}' for user {ctx.user_id}")

    add_context_message(
        ctx,
        ContextMessage(
            role=SYSTEM,
            content=f"💡 Contextual Reminder: {reminder.text}",
            memory_metadata=[to_recalled_memory_metadata(reminder)],
            chat_model=ctx.chat_model.name,
        ),
    )

    # Deactivate non-recurring reminders after triggering
    if not reminder.is_recurring:
        reminder.is_active = False
        ctx.db.commit()
        ctx.db.refresh(reminder)

    return reminder.text
