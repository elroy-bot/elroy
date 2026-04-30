from ...core.turn import TurnContext
from ..context_messages.factory import build_context_refresh_orchestrator
from ..context_messages.session import build_context_message_session
from .session import UserSession, build_user_session
from .store import UserPreferenceStore
from .user_preference_orchestrator import UserPreferenceOrchestrator


def build_user_preference_store(user_session: UserSession) -> UserPreferenceStore:
    return UserPreferenceStore(user_session.db, user_session.user_id)


def _build_user_preference_orchestrator(
    user_session: UserSession,
    refresh_system_instructions_fn,
) -> UserPreferenceOrchestrator:
    return UserPreferenceOrchestrator(
        db=user_session.db,
        user_id=user_session.user_id,
        refresh_system_instructions_fn=refresh_system_instructions_fn,
    )


def build_user_preference_orchestrator(turn: TurnContext) -> UserPreferenceOrchestrator:
    context_refresh_orchestrator = build_context_refresh_orchestrator(build_context_message_session(turn))
    user_session = build_user_session(turn)
    return _build_user_preference_orchestrator(
        user_session,
        refresh_system_instructions_fn=lambda: context_refresh_orchestrator.refresh_system_instructions(),
    )
