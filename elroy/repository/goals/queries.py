from typing import List, Optional

from sqlmodel import select
from toolz import pipe
from toolz.curried import filter

from ...config.constants import RecoverableToolError, allow_unused, tool
from ...config.ctx import ElroyContext
from ...db.db_models import Goal
from ...utils.utils import first_or_none


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


def get_db_goal_by_name(ctx: ElroyContext, name: str) -> Optional[Goal]:
    return pipe(
        get_active_goals(ctx),
        filter(lambda g: g.name == name),
        first_or_none,
    )  # type: ignore


def get_active_goal_names(ctx: ElroyContext) -> List[str]:
    """Gets the list of names for all active goals

    Returns:
        List[str]: List of names for all active goals
    """

    return [goal.name for goal in get_active_goals(ctx)]


@allow_unused
def get_goal_by_name(ctx: ElroyContext, goal_name: str) -> Optional[str]:
    """Get the fact for a goal by name

    Args:
        ctx (ElroyContext): context obj
        goal_name (str): Name of the goal

    Returns:
        Optional[str]: The fact for the goal with the given name
    """
    goal = get_db_goal_by_name(ctx, goal_name)
    if goal:
        return goal.to_fact()
    else:
        raise RecoverableToolError(f"Goal '{goal_name}' not found")


@tool
def print_goal(ctx: ElroyContext, goal_name: str) -> str:
    """Prints the goal with the given name. This does NOT create a goal, it only prints the existing goal with the given name if it has been created already.

    Args:
        goal_name (str): Name of the goal to retrieve

    Returns:
        str: The goal's details if found, or an error message if not found
    """
    goal = ctx.db.exec(
        select(Goal).where(
            Goal.user_id == ctx.user_id,
            Goal.name == goal_name,
            Goal.is_active == True,
        )
    ).first()
    if goal:
        return goal.to_fact()
    else:
        raise RecoverableToolError(f"Goal '{goal_name}' not found")
