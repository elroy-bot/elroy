from dataclasses import dataclass

from ...core.turn import TurnContext
from ...db.db_session import DbSession


@dataclass(frozen=True)
class UserSession:
    db: DbSession
    user_id: int


@dataclass(frozen=True)
class UserRuntime:
    default_assistant_name: str


def build_user_session(turn: TurnContext) -> UserSession:
    return UserSession(
        db=turn.db,
        user_id=turn.session.user_id,
    )


def build_user_runtime(turn: TurnContext) -> UserRuntime:
    return UserRuntime(
        default_assistant_name=turn.config.default_assistant_name,
    )
