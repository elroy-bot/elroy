from __future__ import annotations

from dataclasses import dataclass

from ..db.db_manager import DbManager
from ..db.db_session import DbSession
from .ctx import ElroyConfig
from .latency import LatencyTracker


@dataclass(frozen=True)
class ElroySession:
    """Long-lived DB and user identity for one Elroy session."""

    db_manager: DbManager
    user_id: int
    user_token: str


@dataclass(frozen=True)
class TurnContext:
    """Per-turn execution context for DB-backed work."""

    config: ElroyConfig
    session: ElroySession
    db: DbSession
    latency_tracker: LatencyTracker | None = None

    @property
    def user_id(self) -> int:
        return self.session.user_id
