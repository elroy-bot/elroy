from __future__ import annotations

from dataclasses import dataclass, field

from ..db.db_manager import DbManager
from ..db.db_session import DbSession
from .ctx import ElroyConfig
from .latency import LatencyTracker
from .logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RestartRequest:
    """A pending request to restart the active Elroy app session."""

    resume_prompt: str


@dataclass
class SessionRestartState:
    """Mutable restart state shared across turns in a single Elroy session."""

    supported: bool = False
    _pending_request: RestartRequest | None = None

    def enable(self) -> None:
        self.supported = True
        logger.debug("Session restart support enabled")

    def request(self, resume_prompt: str) -> RestartRequest:
        from .constants import RecoverableToolError

        if not self.supported:
            raise RecoverableToolError("Session restart is not available in this Elroy runtime.")
        request = RestartRequest(resume_prompt=resume_prompt)
        self._pending_request = request
        logger.info("Session restart requested")
        logger.debug("Stored pending restart request with resume_prompt=%r", resume_prompt)
        return request

    def consume(self) -> RestartRequest | None:
        request = self._pending_request
        self._pending_request = None
        logger.debug("Consumed pending restart request: found=%s", request is not None)
        return request


@dataclass(frozen=True)
class ElroySession:
    """Long-lived DB and user identity for one Elroy session."""

    db_manager: DbManager
    user_id: int
    user_token: str
    restart_state: SessionRestartState = field(default_factory=SessionRestartState)


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
