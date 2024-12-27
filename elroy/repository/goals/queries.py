from typing import List

from sqlmodel import select
from toolz import pipe
from toolz.curried import map

from ...config.ctx import ElroyContext
from ...db.db_models import Goal


def get_active_goals_summary(ctx: ElroyContext) -> str:
    """
    Retrieve a summary of active goals for a given user.

    Args:
        session (Session): The database session.
        user_id (int): The ID of the user.

    Returns:
        str: A formatted string summarizing the active goals.
    """
    return pipe(
        get_active_goals(ctx),
        map(lambda x: x.to_fact()),
        list,
        "\n\n".join,
    )  # type: ignore


def get_active_goals(ctx: ElroyContext) -> List[Goal]:
    """
    Retrieve active goals for a given user.

    Args:
        session (Session): The database session.
        user_id (int): The ID of the user.

    Returns:
        List[Goal]: A list of active goals.
    """
    return ctx.db.exec(
        select(Goal)
        .where(
            Goal.user_id == ctx.user_id,
            Goal.is_active == True,
        )
        .order_by(Goal.priority)  # type: ignore
    ).all()
