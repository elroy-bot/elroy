from datetime import UTC

from sqlmodel import select

from ..core.constants import USER
from ..core.ctx import ElroyContext
from ..db.db_models import Message
from ..repository.context_messages.operations import (
    get_refreshed_system_message,
    replace_context_messages,
)
from ..repository.user.queries import do_get_user_preferred_name
from ..utils.clock import local_now, local_tz, today_start_local
from ..utils.utils import datetime_to_string


def get_session_context(ctx: ElroyContext) -> str:
    preferred_name = do_get_user_preferred_name(ctx.db.session, ctx.user_id)

    if preferred_name == "Unknown":
        preferred_name = "User (preferred name unknown)"

    # Include current date/time in session context
    current_datetime = datetime_to_string(local_now())

    today_start = today_start_local()

    # Convert to UTC for database comparison
    today_start_utc = today_start.astimezone(UTC)

    earliest_today_msg = ctx.db.exec(
        select(Message)
        .where(Message.user_id == ctx.user_id)
        .where(Message.role == USER)
        .where(Message.created_at >= today_start_utc)
        .order_by(Message.created_at)  # type: ignore
        .limit(1)
    ).first()

    if earliest_today_msg:
        # Convert UTC time to local timezone for display
        local_time = earliest_today_msg.created_at.replace(tzinfo=UTC).astimezone(local_tz())
        return f"Current date/time: {current_datetime}. {preferred_name} has logged in. I first started chatting with {preferred_name} today at {local_time.strftime('%I:%M %p')}."
    else:
        return f"Current date/time: {current_datetime}. {preferred_name} has logged in. I haven't chatted with {preferred_name} yet today. I should offer a brief greeting (less than 50 words)."


def onboard_non_interactive(ctx: ElroyContext) -> None:
    replace_context_messages(ctx, [get_refreshed_system_message(ctx)])
