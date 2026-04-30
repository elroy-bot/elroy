from dataclasses import dataclass

from ...core.turn import TurnContext
from ...db.db_session import DbSession
from ..user.session import UserRuntime, UserSession, build_user_runtime, build_user_session


@dataclass(frozen=True)
class ContextMessageSession:
    turn: TurnContext
    db: DbSession
    user_id: int
    user_session: UserSession
    user_runtime: UserRuntime


def build_context_message_session(turn: TurnContext) -> ContextMessageSession:
    user_session = build_user_session(turn)
    user_runtime = build_user_runtime(turn)
    return ContextMessageSession(
        turn=turn,
        db=user_session.db,
        user_id=user_session.user_id,
        user_session=user_session,
        user_runtime=user_runtime,
    )
