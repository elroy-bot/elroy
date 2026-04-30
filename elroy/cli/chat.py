from datetime import UTC

from sqlmodel import select

from ..core.constants import USER
from ..core.ctx import ElroyConfig
from ..core.session import build_elroy_session, open_turn_context
from ..core.turn import TurnContext
from ..db.db_models import Message
from ..repository.context_messages.factory import build_context_refresh_orchestrator
from ..repository.context_messages.session import build_context_message_session
from ..repository.user.queries import do_get_user_preferred_name
from ..repository.user.session import build_user_session
from ..utils.clock import local_now, local_tz, today_start_local
from ..utils.utils import datetime_to_string


def get_session_context(turn: TurnContext) -> str:
    user_session = build_user_session(turn)
    preferred_name = do_get_user_preferred_name(user_session.db.session, user_session.user_id)

    if preferred_name == "Unknown":
        preferred_name = "User (preferred name unknown)"

    # Include current date/time in session context
    current_datetime = datetime_to_string(local_now())

    today_start = today_start_local()

    # Convert to UTC for database comparison
    today_start_utc = today_start.astimezone(UTC)

    earliest_today_msg = user_session.db.exec(
        select(Message)
        .where(Message.user_id == user_session.user_id)
        .where(Message.role == USER)
        .where(Message.created_at >= today_start_utc)
        .order_by(Message.created_at)  # type: ignore
        .limit(1)
    ).first()

    if earliest_today_msg:
        # Convert UTC time to local timezone for display
        local_time = earliest_today_msg.created_at.replace(tzinfo=UTC).astimezone(local_tz())
        return f"Current date/time: {current_datetime}. {preferred_name} has logged in. I first started chatting with {preferred_name} today at {local_time.strftime('%I:%M %p')}."
    return f"Current date/time: {current_datetime}. {preferred_name} has logged in. I haven't chatted with {preferred_name} yet today. I should offer a brief greeting (less than 50 words)."


def get_session_context_from_ctx(ctx: ElroyConfig) -> str:
    with open_turn_context(ctx, build_elroy_session(ctx)) as turn:
        return get_session_context(turn)


def onboard_non_interactive(turn: TurnContext) -> None:
    context_refresh_orchestrator = build_context_refresh_orchestrator(build_context_message_session(turn))
    context_refresh_orchestrator.store.replace_context_messages([context_refresh_orchestrator.get_refreshed_system_message()])
