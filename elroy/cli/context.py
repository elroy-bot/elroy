import asyncio
import logging
from datetime import datetime

from pytz import UTC
from sqlmodel import select

from ..config.constants import USER
from ..config.ctx import ElroyContext, clone_ctx_with_db
from ..db.db_models import Message
from ..messaging.context import context_refresh
from ..tools.user_preferences import get_user_preferred_name
from ..utils.utils import datetime_to_string


def periodic_context_refresh(ctx: ElroyContext):
    """Run context refresh in a background thread"""
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def refresh_loop(ctx: ElroyContext):
        logging.info(f"Pausing for initial context refresh wait of {ctx.initial_refresh_wait}")
        await asyncio.sleep(ctx.initial_refresh_wait.total_seconds())
        while True:
            try:
                logging.info("Refreshing context")
                await context_refresh(ctx)  # Keep this async
                logging.info(f"Wait for {ctx.context_refresh_interval} before next context refresh")
                await asyncio.sleep(ctx.context_refresh_interval.total_seconds())
            except Exception as e:
                logging.error(f"Error in periodic context refresh: {e}")
                ctx.db.rollback()

                if ctx.debug:
                    raise e

    try:
        # hack to get a new session for the thread
        with ctx.db.get_new_session() as db:
            new_ctx = clone_ctx_with_db(ctx, db)
            loop.run_until_complete(refresh_loop(new_ctx))
    finally:
        loop.close()


def get_user_logged_in_message(ctx: ElroyContext) -> str:
    preferred_name = get_user_preferred_name(ctx)

    if preferred_name == "Unknown":
        preferred_name = "User apreferred name unknown)"

    local_tz = datetime.now().astimezone().tzinfo

    # Get start of today in local timezone
    today_start = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

    # Convert to UTC for database comparison
    today_start_utc = today_start.astimezone(UTC)

    earliest_today_msg = ctx.db.exec(
        select(Message)
        .where(Message.role == USER)
        .where(Message.created_at >= today_start_utc)
        .order_by(Message.created_at)  # type: ignore
        .limit(1)
    ).first()

    if earliest_today_msg:
        today_summary = (
            f"I first started chatting with {preferred_name} today at {earliest_today_msg.created_at.astimezone().strftime('%I:%M %p')}."
        )
    else:
        today_summary = f"I haven't chatted with {preferred_name} yet today. I should offer a brief greeting."

    return f"{preferred_name} has logged in. The current time is {datetime_to_string(datetime.now().astimezone())}. {today_summary}"
