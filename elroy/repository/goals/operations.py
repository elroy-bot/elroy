# Should have param for checking if a similar goal already exists
import logging
from typing import Optional

from sqlmodel import select
from toolz import pipe
from toolz.curried import filter

from ...config.ctx import ElroyContext
from ...db.db_models import SYSTEM, Goal
from ...messaging.context import drop_goal_from_current_context, remove_from_context
from ...utils.clock import get_utc_now, string_to_timedelta
from ...utils.utils import first_or_none, is_blank
from ..data_models import ContextMessage
from ..embeddings import upsert_embedding_if_needed
from ..message import add_context_messages
from .queries import get_active_goals


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
        session (Session): The database session.
        user_id (int): user id
        goal_name (str): Name of the goal
        strategy (str): The strategy to achieve the goal. Your strategy should detail either how you (the personal assistant) will achieve the goal, or how you will assist your user to solve the goal. Limit to 100 words.
        description (str): A brief description of the goal. Limit to 100 words.
        end_condition (str): The condition that indicate to you (the personal assistant) that the goal is achieved or terminated. It is critical that this end condition be OBSERVABLE BY YOU (the assistant). For example, the end_condition may be that you've asked the user about the goal status.
        time_to_completion (str): The amount of time from now until the goal can be completed. Should be in the form of NUMBER TIME_UNIT, where TIME_UNIT is one of HOURS, DAYS, WEEKS, MONTHS. For example, "1 DAYS" would be a goal that should be completed within 1 day.
        priority (int): The priority of the goal, from 0-4. Priority 0 is the highest priority, and 4 is the lowest.
    """
    if is_blank(goal_name):
        raise ValueError("Goal name cannot be empty")

    existing_goal = ctx.db.exec(
        select(Goal).where(
            Goal.user_id == ctx.user_id,
            Goal.name == goal_name,
            Goal.is_active == True,
        )
    ).one_or_none()
    if existing_goal:
        raise Exception(f"Active goal {goal_name} already exists for user {ctx.user_id}")
    else:
        goal = Goal(
            user_id=ctx.user_id,
            name=goal_name,
            description=description,
            strategy=strategy,
            end_condition=end_condition,
            priority=priority,
            target_completion_time=get_utc_now() + string_to_timedelta(time_to_completion) if time_to_completion else None,
        )  # type: ignore
        ctx.db.add(goal)
        ctx.db.commit()
        ctx.db.refresh(goal)

        add_context_messages(
            ctx,
            [
                ContextMessage(
                    role=SYSTEM,
                    content=f"New goal created: {goal.to_fact()}",
                    memory_metadata=[goal.to_memory_metadata()],
                    chat_model=ctx.chat_model.name,
                )
            ],
        )

        upsert_embedding_if_needed(ctx, goal)

        return f"Goal '{goal_name}' has been created."


def rename_goal(ctx: ElroyContext, old_goal_name: str, new_goal_name: str) -> str:
    """Renames an existing active goal.

    Args:
        context (ElroyContext): The Elroy context.
        old_goal_name (str): The current name of the goal.
        new_goal_name (str): The new name for the goal.

    Raises:
        Exception: If the goal with old_goal_name doesn't exist or if a goal with new_goal_name already exists.
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
    old_goal.updated_at = get_utc_now()

    ctx.db.commit()
    ctx.db.refresh(old_goal)

    upsert_embedding_if_needed(ctx, old_goal)

    add_context_messages(
        ctx,
        [
            ContextMessage(
                role=SYSTEM,
                content=f"Goal '{old_goal_name}' has been renamed to '{new_goal_name}': {old_goal.to_fact()}",
                memory_metadata=[old_goal.to_memory_metadata()],
                chat_model=ctx.chat_model.name,
            )
        ],
    )
    return f"Goal '{old_goal_name}' has been renamed to '{new_goal_name}'."


def _update_goal_status(ctx: ElroyContext, goal_name: str, is_terminal: bool, status: Optional[str]) -> None:
    active_goals = get_active_goals(ctx)

    goal = pipe(
        active_goals,
        filter(lambda g: g.name == goal_name),
        first_or_none,
    )

    if not goal:
        raise Exception(f"Active goal {goal_name} not found for user. Active goals: " + ", ".join([g.name for g in active_goals]))
    assert isinstance(goal, Goal)

    logging.info(f"Updating goal {goal_name} for user {ctx.user_id}")
    logging.info(f"Current status updates: {goal.status_updates}")

    # Get current status updates and append new one
    status_updates = goal.get_status_updates()
    if status:
        status_updates.append(status)
        goal.set_status_updates(status_updates)

    if is_terminal:
        goal.is_active = None

    logging.info(f"Updated status updates: {goal.status_updates}")

    ctx.db.commit()
    ctx.db.refresh(goal)

    if status:
        assert status in goal.status_updates, "Status update not found in goal status updates"

    upsert_embedding_if_needed(ctx, goal)

    if not goal.is_active:
        remove_from_context(ctx, goal)


def add_goal_status_update(ctx: ElroyContext, goal_name: str, status_update_or_note: str) -> str:
    """Captures either a progress update or note relevant to the goal.

    Args:
        session (Session): The database session.
        user_id (int): The user id
        goal_name (str): Name of the goal
        status_update_or_note (str): A brief status update or note about either progress or learnings relevant to the goal. Limit to 100 words.
    Returns:
        str: Confirmation message
    """
    logging.info(f"Updating goal {goal_name} for user {ctx.user_id}")
    _update_goal_status(ctx, goal_name, False, status_update_or_note)

    return f"Status update added to goal '{goal_name}'."


def create_onboarding_goal(ctx: ElroyContext, preferred_name: str) -> None:

    create_goal(
        ctx=ctx,
        goal_name=f"Introduce myself to {preferred_name}",
        description="Introduce myself - a few things that make me unique are my ability to form long term memories, and the ability to set and track goals.",
        strategy=f"After exchanging some pleasantries, tell {preferred_name} about my ability to form long term memories, including goals. Use function {add_goal_status_update.__name__} with any progress or learnings.",
        end_condition=f"{preferred_name} has been informed about my ability to track goals",
        priority=1,
        time_to_completion="1 HOUR",
    )


def mark_goal_completed(ctx: ElroyContext, goal_name: str, closing_comments: Optional[str] = None) -> str:
    """Marks a goal as completed, with closing comments.

    Args:
        session (Session): The database session.
        user_id (int): The user ID
        goal_name (str): The name of the goal
        closing_comments (str): Updated status with a short account of how the goal was completed and what was learned.
    Returns:
        str: Confirmation message
    """
    _update_goal_status(
        ctx,
        goal_name,
        True,
        closing_comments,
    )

    return f"Goal '{goal_name}' has been marked as completed."


def delete_goal_permanently(ctx: ElroyContext, goal_name: str) -> str:
    """Closes the goal.

    Args:
        session (Session): The database session.
        user_id (int): The user ID
        goal_name (str): The name of the goal
    Returns:
        str: Result of the deletion
    """

    _update_goal_status(
        ctx,
        goal_name,
        True,
        "Goal has been deleted",
    )

    return f"Goal '{goal_name}' has been deleted."
