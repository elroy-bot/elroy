from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, Field
from sqlmodel import select

from ...core.constants import SYSTEM, RecoverableToolError
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import Reminder
from ...llm.client import query_llm_with_response_format
from ...utils.clock import string_to_datetime
from ...utils.utils import is_blank
from ..context_messages.data_models import ContextMessage
from ..context_messages.operations import add_context_message
from ..recall.operations import (
    remove_from_context,
    upsert_embedding_if_needed,
)
from ..recall.transforms import to_recalled_memory_metadata
from .queries import get_active_reminders, get_db_reminder_by_name
from .tools import create_reminder as create_reminder_tool

logger = get_logger()


class ReminderAlreadyExistsError(RecoverableToolError):
    def __init__(self, reminder_name: str, reminder_type: str):
        super().__init__(f"{reminder_type} reminder '{reminder_name}' already exists")


class ReminderDoesNotExistError(RecoverableToolError):
    def __init__(self, reminder_name: str, reminder_type: str, available_names: list):
        super().__init__(f"{reminder_type} reminder '{reminder_name}' not found. Available: {', '.join(available_names)}")


def do_create_reminder(ctx: ElroyContext, name: str, description: str) -> Reminder:

    class CreateTimedReminderRequest(BaseModel):
        name: str = Field(description="Short name for the reminder")
        text: str = Field(description="Content of the reminder")
        trigger_time: str = Field(
            description="Time the reminder should be sent, in ISO 8601 format without timezone. Be as specific as is appropriate. Assume datetime is in user's time zone."
        )

    class CreateContextualReminderRequest(BaseModel):
        name: str = Field(description="Short name for the reminder")
        text: str = Field(description="Content of the reminder")
        reminder_context: str = Field(description="A description of the situation in which the reminder should be sent.")

    class CreateReminderRequest(BaseModel):
        timed_reminder_request: Optional[CreateTimedReminderRequest] = Field(description="Request for a timed reminder")
        contextual_reminder_request: Optional[CreateContextualReminderRequest] = Field(description="Request for a contextual reminder")

    req = query_llm_with_response_format(
        ctx.chat_model,
        system="""Your task is to translate user text into API call params. The reminder should be either a timed reminder, which should be sent to the user at a specific time, or a contextual remidner, which should be sent to the user when a certain situation arises. Your response should contain ONE OF CreateTimedReminderRequest, or CreateContextualReminderRequest""",
        prompt=f"#{name}\n#{description}",
        response_format=CreateReminderRequest,
    )

    if req.timed_reminder_request:
        # parse time assuming ISO 8601 format
        reminder_time = string_to_datetime(req.timed_reminder_request.trigger_time)

        create_reminder_tool(
            ctx=ctx, name=req.timed_reminder_request.name, text=req.timed_reminder_request.text, trigger_time=reminder_time.strftime("%Y-%m-%d %H:%M")
        )
        
        # Return the created reminder
        return get_db_reminder_by_name(ctx, req.timed_reminder_request.name)

    elif req.contextual_reminder_request:
        create_reminder_tool(
            ctx=ctx,
            name=req.contextual_reminder_request.name,
            text=req.contextual_reminder_request.text,
            reminder_context=req.contextual_reminder_request.reminder_context,
        )
        
        # Return the created reminder
        return get_db_reminder_by_name(ctx, req.contextual_reminder_request.name)

    else:
        raise ValueError("Request must contain either a timed or contextual reminder")




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


def trigger_reminder(ctx: ElroyContext, reminder: Reminder) -> str:
    """Trigger a reminder and optionally deactivate it

    Args:
        ctx (ElroyContext): The Elroy context
        reminder (Reminder): The reminder to trigger

    Returns:
        str: The reminder text that was triggered
    """
    reminder_type = "timed" if reminder.trigger_datetime else "contextual"
    logger.info(f"Triggering {reminder_type} reminder '{reminder.name}' for user {ctx.user_id}")

    # Choose appropriate emoji and message format
    if reminder.trigger_datetime:
        emoji = "⏰"
        message_type = "Reminder"
    else:
        emoji = "💡"
        message_type = "Contextual Reminder"

    add_context_message(
        ctx,
        ContextMessage(
            role=SYSTEM,
            content=f"{emoji} {message_type}: {reminder.text}",
            memory_metadata=[to_recalled_memory_metadata(reminder)],
            chat_model=ctx.chat_model.name,
        ),
    )

    # Deactivate reminders after triggering
    reminder.is_active = None
    ctx.db.commit()
    ctx.db.refresh(reminder)

    return reminder.text
