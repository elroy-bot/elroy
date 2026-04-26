from ...core.ctx import ElroyContext
from ...core.db import require_db_session
from ..context_messages.factory import build_context_refresh_orchestrator
from .store import UserPreferenceStore
from .user_preference_orchestrator import UserPreferenceOrchestrator


def build_user_preference_store(ctx: ElroyContext) -> UserPreferenceStore:
    return UserPreferenceStore(require_db_session(ctx), ctx.user_id)


def build_user_preference_orchestrator(ctx: ElroyContext) -> UserPreferenceOrchestrator:
    context_refresh_orchestrator = build_context_refresh_orchestrator(ctx)
    return UserPreferenceOrchestrator(
        db=require_db_session(ctx),
        user_id=ctx.user_id,
        refresh_system_instructions_fn=lambda: context_refresh_orchestrator.refresh_system_instructions(),
    )
