# Should have param for checking if a similar goal already exists
from typing import Optional

from sqlmodel import select

from ...core.constants import SYSTEM, GoalAlreadyExistsError, GoalDoesNotExistError
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import Goal
from ...utils.clock import get_utc_now, string_to_timedelta
from ...utils.utils import is_blank
from ..context_messages.data_models import ContextMessage
from ..context_messages.operations import add_context_message
from ..recall.operations import (
    add_to_context,
    remove_from_context,
    upsert_embedding_if_needed,
)
from ..recall.transforms import to_recalled_memory_metadata
from .queries import get_active_goals, get_db_goal_by_name

logger = get_logger()


def do_create_goal(
    ctx: ElroyContext,
    goal_name: str,
    strategy: Optional[str] = None,
    description: Optional[str] = None,
    end_condition: Optional[str] = None,
    time_to_completion: Optional[str] = None,
    priority: Optional[int] = None,
) -> Goal:
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
        raise GoalAlreadyExistsError(goal_name)
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

        add_context_message(
            ctx,
            ContextMessage(
                role=SYSTEM,
                content=f"New goal created: {goal.to_fact()}",
                memory_metadata=[to_recalled_memory_metadata(goal)],
                chat_model=ctx.chat_model.name,
            ),
        )

        upsert_embedding_if_needed(ctx, goal)
        return goal


def create_onboarding_goal(ctx: ElroyContext, preferred_name: str) -> None:
    from elroy.repository.goals.tools import add_goal_status_update

    do_create_goal(
        ctx=ctx,
        goal_name=f"Introduce myself to {preferred_name}",
        description="Introduce myself - a few things that make me unique are my ability to form long term memories, and the ability to set and track goals.",
        strategy=f"After exchanging some pleasantries, tell {preferred_name} about my ability to form long term memories, including goals. Use function {add_goal_status_update.__name__} with any progress or learnings.",
        end_condition=f"{preferred_name} has been informed about my ability to track goals",
        priority=1,
        time_to_completion="1 HOUR",
    )


def update_goal_status(ctx: ElroyContext, goal_name: str, is_terminal: bool, status: Optional[str]) -> None:
    from ..memories.operations import do_create_memory

    goal = get_db_goal_by_name(ctx, goal_name)

    if not goal:
        raise GoalDoesNotExistError(goal_name, [g.name for g in get_active_goals(ctx)])
    assert isinstance(goal, Goal)

    logger.info(f"Updating goal {goal_name} for user {ctx.user_id}")
    logger.info(f"Current status updates: {goal.status_updates}")

    # Get current status updates and append new one
    status_updates = goal.get_status_updates()
    if status:
        status_updates.append(status)
        goal.set_status_updates(status_updates)

    if is_terminal:
        goal.is_active = None
        remove_from_context(ctx, goal)
        do_create_memory(
            ctx,
            "Completed Goal: " + goal_name,
            goal.to_fact(),
            [goal],
            True,
        )
    else:
        add_to_context(ctx, goal)

    logger.info(f"Updated status updates: {goal.status_updates}")

    ctx.db.commit()
    ctx.db.refresh(goal)

    upsert_embedding_if_needed(ctx, goal)
