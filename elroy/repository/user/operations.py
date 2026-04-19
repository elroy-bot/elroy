from ...core.constants import user_only_tool
from ...core.ctx import ElroyContext
from ...db.db_models import UserPreference
from ...db.db_session import DbSession
from .user_preference_orchestrator import UserPreferenceOrchestrator


def _orchestrator(ctx: ElroyContext) -> UserPreferenceOrchestrator:
    from ..context_messages.operations import refresh_system_instructions

    return UserPreferenceOrchestrator(
        db=ctx.db,
        user_id=ctx.user_id,
        refresh_system_instructions_fn=lambda: refresh_system_instructions(ctx),
    )


def get_or_create_user_preference(ctx: ElroyContext) -> UserPreference:
    return _orchestrator(ctx).get_or_create_user_preference()


def create_user_id(db: DbSession, user_token: str) -> int:
    from .store import create_user_id as create_user_id_in_store

    return create_user_id_in_store(db, user_token)


@user_only_tool
def set_assistant_name(ctx: ElroyContext, assistant_name: str) -> str:
    """
    Sets the assistant name for the user
    """
    return _orchestrator(ctx).set_assistant_name(assistant_name)


def reset_system_persona(ctx: ElroyContext) -> str:
    """
    Clears the system instruction for the user
    """
    return _orchestrator(ctx).reset_system_persona()


def set_persona(ctx: ElroyContext, system_persona: str) -> str:
    """
    Sets the system instruction for the user
    """
    return _orchestrator(ctx).set_persona(system_persona)
