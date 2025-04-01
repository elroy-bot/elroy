from typing import Optional

from sqlmodel import select
from toolz import pipe
from toolz.curried import filter

from ...core.constants import SYSTEM, RecoverableToolError, tool
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import Goal
from ...utils.clock import utc_now
from ...utils.utils import first_or_none
from ..context_messages.data_models import ContextMessage
from ..context_messages.operations import add_context_message
from ..context_messages.tools import drop_goal_from_current_context
from ..recall.operations import upsert_embedding_if_needed
from ..recall.transforms import to_recalled_memory_metadata
from .operations import do_create_goal, update_goal_status
from .queries import get_active_goal_names, get_active_goals

logger = get_logger()


@tool
def create_goal(
    ctx: ElroyContext,
    goal_name: str,
    strategy: Optional[str] = None,
    description: Optional[str] = None,
    end_condition: Optional[str] = None,
    time_to_completion: Optional[str] = None,
    priority: Optional[int] = None,
) -> str:
    """Creates a goal. The goal can be for the AI user, or for the assistant in relation to helping the user somehow.
    Goals should be *specific* and *measurable*. They should be based on the user's needs and desires, and should
    be achievable within a reasonable timeframe.

    Args:
        goal_name (str): Name of the goal
        strategy (str): The strategy to achieve the goal. Your strategy should detail either how you (the personal assistant) will achieve the goal, or how you will assist your user to solve the goal. Limit to 100 words.
        description (str): A brief description of the goal. Limit to 100 words.
        end_condition (str): The condition that indicate to you (the personal assistant) that the goal is achieved or terminated. It is critical that this end condition be OBSERVABLE BY YOU (the assistant). For example, the end_condition may be that you've asked the user about the goal status.
        time_to_completion (str): The amount of time from now until the goal can be completed. Should be in the form of NUMBER TIME_UNIT, where TIME_UNIT is one of HOURS, DAYS, WEEKS, MONTHS. For example, "1 DAYS" would be a goal that should be completed within 1 day.
        priority (int, optional): The priority of the goal, from 0-4. Priority 0 is the highest priority, and 4 is the lowest.

    Returns:
        str: A confirmation message that the goal was created.

    Raises:
        ValueError: If goal_name is empty
        GoalAlreadyExistsError: If a goal with the same name already exists
    """
    do_create_goal(
        ctx,
        goal_name,
        strategy,
        description,
        end_condition,
        time_to_completion,
        priority,
    )
    return f"Goal '{goal_name}' has been created."


@tool
def rename_goal(ctx: ElroyContext, old_goal_name: str, new_goal_name: str) -> str:
    """Renames an existing active goal.

    Args:
        old_goal_name (str): The current name of the goal
        new_goal_name (str): The new name for the goal

    Returns:
        str: A confirmation message that the goal was renamed

    Raises:
        GoalDoesNotExistError: If the goal with old_goal_name doesn't exist
        Exception: If a goal with new_goal_name already exists
    """
    # Check if the old goal exists and is active
    active_goals = get_active_goals(ctx)
    old_goal = pipe(
        active_goals,
        filter(lambda g: g.name == old_goal_name),
        first_or_none,
    )

    if not old_goal:
        raise Exception(
            f"Active goal '{old_goal_name}' not found for user {ctx.user_id}. Active goals: " + ", ".join([g.name for g in active_goals])
        )

    existing_goal_with_new_name = pipe(
        active_goals,
        filter(lambda g: g.name == new_goal_name),
        first_or_none,
    )

    assert isinstance(old_goal, Goal)

    if existing_goal_with_new_name:
        raise Exception(f"Active goal '{new_goal_name}' already exists for user {ctx.user_id}")

    # we need to drop the goal from context as the metadata includes the goal name.
    drop_goal_from_current_context(ctx, old_goal.name)

    # Rename the goal
    old_goal.name = new_goal_name
    old_goal.updated_at = utc_now()  # noqa F841

    ctx.db.commit()
    ctx.db.refresh(old_goal)

    upsert_embedding_if_needed(ctx, old_goal)

    add_context_message(
        ctx,
        ContextMessage(
            role=SYSTEM,
            content=f"Goal '{old_goal_name}' has been renamed to '{new_goal_name}': {old_goal.to_fact()}",
            memory_metadata=[to_recalled_memory_metadata(old_goal)],
            chat_model=ctx.chat_model.name,
        ),
    )
    return f"Goal '{old_goal_name}' has been renamed to '{new_goal_name}'."


@tool
def add_goal_status_update(ctx: ElroyContext, goal_name: str, status_update_or_note: str) -> str:
    """Captures either a progress update or note relevant to the goal.

    Args:
        goal_name (str): Name of the goal
        status_update_or_note (str): A brief status update or note about either progress or learnings relevant to the goal. Limit to 100 words.

    Returns:
        str: Confirmation message that the status update was added.
    """
    logger.info(f"Updating goal {goal_name} for user {ctx.user_id}")
    update_goal_status(ctx, goal_name, False, status_update_or_note)

    return f"Status update added to goal '{goal_name}'."


@tool
def mark_goal_completed(ctx: ElroyContext, goal_name: str, closing_comments: Optional[str] = None) -> str:
    """Marks a goal as completed, with closing comments.

    Args:
        goal_name (str): The name of the goal
        closing_comments (Optional[str]): Updated status with a short account of how the goal was completed and what was learned

    Returns:
        str: Confirmation message that the goal was marked as completed

    Raises:
        GoalDoesNotExistError: If the goal doesn't exist
    """
    update_goal_status(
        ctx,
        goal_name,
        True,
        closing_comments,
    )

    return f"Goal '{goal_name}' has been marked as completed."


@tool
def delete_goal_permanently(ctx: ElroyContext, goal_name: str) -> str:
    """Permanently deletes a goal.

    Args:
        goal_name (str): The name of the goal to delete

    Returns:
        str: Confirmation message that the goal was deleted

    Raises:
        GoalDoesNotExistError: If the goal doesn't exist
    """

    update_goal_status(
        ctx,
        goal_name,
        True,
        "Goal has been deleted",
    )

    return f"Goal '{goal_name}' has been deleted."


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
        valid_goals = ",".join(sorted(get_active_goal_names(ctx)))
        raise RecoverableToolError(f"Goal '{goal_name}' not found. Valid goals: {valid_goals}")
