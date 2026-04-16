from ...core.ctx import ElroyContext
from ..context_messages.factory import build_context_refresh_orchestrator
from .user_preference_orchestrator import UserPreferenceOrchestrator


def build_user_preference_orchestrator(ctx: ElroyContext) -> UserPreferenceOrchestrator:
    context_refresh_orchestrator = build_context_refresh_orchestrator(ctx)
    return UserPreferenceOrchestrator(
        db=ctx.db,
        user_id=ctx.user_id,
        refresh_system_instructions_fn=lambda: context_refresh_orchestrator.refresh_system_instructions(),
    )
