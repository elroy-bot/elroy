import asyncio
from datetime import datetime

from pytz import UTC
from sqlmodel import select

from ..config.constants import USER
from ..config.ctx import ElroyContext
from ..db.db_models import Message
from ..messaging.context import context_refresh, is_context_refresh_needed
from ..tools.user_preferences import get_user_preferred_name
from ..utils.utils import datetime_to_string


def refresh_context_if_needed(ctx: ElroyContext):
    if is_context_refresh_needed(ctx):
        asyncio.run(context_refresh(ctx))


def get_user_logged_in_message(ctx: ElroyContext) -> str:
    preferred_name = get_user_preferred_name(ctx)

    if preferred_name == "Unknown":
        preferred_name = "User (preferred name unknown)"

    local_tz = datetime.now().astimezone().tzinfo

    # Get start of today in local timezone
    today_start = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

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
        local_time = earliest_today_msg.created_at.replace(tzinfo=UTC).astimezone(local_tz)
        today_summary = f"I first started chatting with {preferred_name} today at {local_time.strftime('%I:%M %p')}."
    else:
        today_summary = f"I haven't chatted with {preferred_name} yet today. I should offer a brief greeting."

    return f"{preferred_name} has logged in. The current time is {datetime_to_string(datetime.now().astimezone())}. {today_summary}"
