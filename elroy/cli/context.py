import asyncio
import logging
from datetime import datetime

from pytz import UTC
from sqlmodel import select

from ..config.config import ElroyContext, session_manager
from ..config.constants import CLI_USER_ID
from ..messaging.context import context_refresh
from ..repository.data_models import USER, Message
from ..tools.user_preferences import get_user_preferred_name
from ..utils.utils import datetime_to_string


def periodic_context_refresh(context: ElroyContext):
    """Run context refresh in a background thread"""
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def refresh_loop(context: ElroyContext):
        logging.info(f"Pausing for initial context refresh wait of {context.config.initial_refresh_wait}")
        await asyncio.sleep(context.config.initial_refresh_wait.total_seconds())
        while True:
            try:
                logging.info("Refreshing context")
                await context_refresh(context)  # Keep this async
                logging.info(f"Wait for {context.config.context_refresh_interval} before next context refresh")
                await asyncio.sleep(context.config.context_refresh_interval.total_seconds())
            except Exception as e:
                logging.error(f"Error in periodic context refresh: {e}")
                context.session.rollback()

                if context.config.debug_mode:
                    raise e

    try:
        # hack to get a new session for the thread
        with session_manager(context.config.postgres_url) as session:
            loop.run_until_complete(
                refresh_loop(
                    ElroyContext(
                        user_id=CLI_USER_ID,
                        session=session,
                        config=context.config,
                        io=context.io,
                    )
                )
            )
    finally:
        loop.close()


def get_user_logged_in_message(context: ElroyContext) -> str:
    preferred_name = get_user_preferred_name(context)

    if preferred_name == "Unknown":
        preferred_name = "User apreferred name unknown)"

    local_tz = datetime.now().astimezone().tzinfo

    # Get start of today in local timezone
    today_start = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)

    # Convert to UTC for database comparison
    today_start_utc = today_start.astimezone(UTC)

    earliest_today_msg = context.session.exec(
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
