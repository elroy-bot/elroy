import typer
from sqlmodel import Session, select
from toolz import do, pipe
from toolz.curried import do

from ...core.constants import user_only_tool
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import User, UserPreference
from ...db.db_session import DbSession
from ...utils.utils import is_blank

logger = get_logger()


def create_user_id(db: DbSession, user_token: str) -> int:
    return pipe(
        User(token=user_token),
        do(db.add),
        do(lambda _: db.commit()),
        do(db.refresh),
        lambda user: user.id,
    )  # type: ignore


def get_or_create_user_preference(ctx: ElroyContext) -> UserPreference:
    return do_get_or_create_user_preference(ctx.db.session, ctx.user_id)


def do_get_or_create_user_preference(session: Session, user_id: int) -> UserPreference:
    user_preference = session.exec(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.is_active == True,
        )
    ).first()

    if user_preference is None:
        user_preference = UserPreference(user_id=user_id, is_active=True)
        session.add(user_preference)
        session.commit()
        session.refresh(user_preference)
    return user_preference


@user_only_tool
def set_assistant_name(ctx: ElroyContext, assistant_name: str) -> str:
    """
    Sets the assistant name for the user
    """

    ctx.set_assistant_name(assistant_name)
    return f"Assistant name updated to {assistant_name}."


def reset_system_persona(ctx: ElroyContext) -> str:
    """
    Clears the system instruction for the user
    """
    from ..context_messages.operations import refresh_system_instructions

    user_preference = get_or_create_user_preference(ctx)
    if not user_preference.system_persona:
        # Re-clear the persona even if it was already blank, in case some malformed value has been set
        logger.warning("System persona was already set to default")

    user_preference.system_persona = None

    ctx.db.add(user_preference)
    ctx.db.commit()

    refresh_system_instructions(ctx)
    return "System persona cleared, will now use default persona."


def set_persona(ctx: ElroyContext, system_persona: str) -> str:
    """
    Sets the system instruction for the user
    """
    from ..context_messages.operations import refresh_system_instructions

    system_persona = system_persona.strip()

    if is_blank(system_persona):
        raise typer.BadParameter("System persona cannot be blank.")

    user_preference = get_or_create_user_preference(ctx)

    if user_preference.system_persona == system_persona:
        return do(
            logger.info,
            "New system persona and old system persona are identical",
        )  # type: ignore

    user_preference.system_persona = system_persona

    ctx.db.add(user_preference)
    ctx.db.commit()

    refresh_system_instructions(ctx)
    return "System persona updated."
