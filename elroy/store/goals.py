import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlmodel import select, update
from toolz import first, pipe
from toolz.curried import filter, map

from elroy.config import ElroyContext
from elroy.store.data_models import ContextMessage, Fact, Goal, convert_to_utc
from elroy.store.embeddings import upsert_embedding
from elroy.system.clock import get_utc_now, string_to_timedelta
from elroy.system.parameters import GOAL_CHECKIN_COUNT


def get_goals_with_due_status(context: ElroyContext) -> List[Goal]:
    """
    Retrieve goals with due status for a given user.

    Args:
        session (Session): The database session.
        user_id (int): The ID of the user.

    Returns:
        List[Goal]: A list of goals with due status.
    """
    goals = context.session.exec(
        select(Goal).where(
            Goal.user_id == context.user_id,
            Goal.is_active == True,
        )
    ).all()

    return pipe(
        goals,
        filter(
            lambda goal: _current_checkin_due_datetime(goal) < convert_to_utc(goal.updated_at),
        ),
        list,
    )  # type: ignore


def _current_checkin_due_datetime(goal: Goal) -> datetime:
    """
    Returns the most recent due datetime for the goal check-in.

    Args:
        goal (Goal): The goal object.

    Returns:
        datetime: The due datetime for the next check-in, in UTC.
    """
    # returns the due datetime for the next checkin, in UTC
    if not goal.target_completion_time:
        logging.warning(f"Goal {goal.name} has no target completion time, specifying arbitrary future checkin time")
        return get_utc_now() + timedelta(weeks=100)

    return pipe(
        goal.target_completion_time - goal.created_at,
        lambda _: [i * (_ / GOAL_CHECKIN_COUNT) for i in range(GOAL_CHECKIN_COUNT + 1)],
        map(lambda _: convert_to_utc(goal.created_at + _)),
        filter(lambda _: _ < get_utc_now()),
        first,
    )  # type: ignore


def create_goal(
    context: ElroyContext,
    goal_name: str,
    strategy: str,
    description: str,
    end_condition: str,
    time_to_completion: Optional[str] = None,
    priority: Optional[int] = None,
) -> None:
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
    existing_goal = context.session.exec(
        select(Goal).where(
            Goal.user_id == context.user_id,
            Goal.name == goal_name,
            Goal.is_active == True,
        )
    ).one_or_none()
    if existing_goal:
        raise Exception(f"Active goal {goal_name} already exists for user {context.user_id}")
    else:
        goal = Goal(
            user_id=context.user_id,
            name=goal_name,
            description=description,
            strategy=strategy,
            end_condition=end_condition,
            priority=priority,
            target_completion_time=get_utc_now() + string_to_timedelta(time_to_completion) if time_to_completion else None,
        )
        context.session.add(goal)
        context.session.commit()
        context.session.refresh(goal)

        from elroy.store.message import add_context_messages

        add_context_messages(
            context,
            [
                ContextMessage(
                    role="system",
                    content=f"Goal '{goal_name}' has been created. {description}. {strategy}. {end_condition}.",
                    memory_metadata=[goal.to_memory_metadata()],
                )
            ],
        )

        upsert_embedding(context.session, goal)


def create_onboarding_goal(context: ElroyContext, preferred_name: str) -> None:

    create_goal(
        context=context,
        goal_name=f"Introduce myself to {preferred_name}",
        description="Introduce myself - a few things that make me unique are my ability to form long term memories, and the ability to set and track goals.",
        strategy=f"After exchanging some pleasantries, tell {preferred_name} about my ability to form long term memories, including goals. Use function {add_goal_status_update.__name__} with any progress or learnings.",
        end_condition=f"{preferred_name} has been informed about my ability to track goals",
        priority=1,
        time_to_completion="1 HOUR",
    )


def add_goal_status_update(context: ElroyContext, goal_name: str, status_update_or_note: str) -> None:
    """Captures either a progress update or note relevant to the goal.

    Args:
        session (Session): The database session.
        user_id (int): The user id
        goal_name (str): Name of the goal
        status_update_or_note (str): A brief status update or note about either progress or learnings relevant to the goal. Limit to 100 words.
    """
    logging.info(f"Updating goal {goal_name} for user {context.user_id}")
    _update_goal_status(context, goal_name, status_update_or_note, False)


def mark_goal_completed(context: ElroyContext, goal_name: str, closing_comments: str) -> None:
    """Marks a goal as completed, with closing comments.

    Args:
        session (Session): The database session.
        user_id (int): The user ID
        goal_name (str): The name of the goal
        closing_comments (str): Updated status with a short account of how the goal was completed and what was learned.
    """
    _update_goal_status(
        context,
        goal_name,
        closing_comments,
        True,
    )


def _update_goal_status(context: ElroyContext, goal_name: str, status: str, is_terminal: bool) -> None:
    goal = context.session.exec(
        select(Goal).where(
            Goal.user_id == context.user_id,
            Goal.name == goal_name,
            Goal.is_active == True,
        )
    ).first()
    if not goal:
        raise Exception(f"Active goal {goal_name} not found for user {context.user_id}")

    logging.info(f"Updating goal {goal_name} for user {context.user_id}")
    logging.info(f"Current status updates: {goal.status_updates}")

    # Append the new status update to the list
    if goal.status_updates is None:
        goal.status_updates = []
    goal.status_updates.append(status)

    logging.info(f"Updated status updates: {goal.status_updates}")

    # Update the goal's active status if it's terminal
    if is_terminal:
        goal.is_active = False

    goal.updated_at = get_utc_now()

    # Explicitly update the status_updates column, the recommended style has a bug
    context.session.execute(
        update(Goal)
        .where(Goal.id == goal.id)  # type: ignore
        .values(status_updates=goal.status_updates, is_active=goal.is_active, updated_at=goal.updated_at)
    )

    context.session.commit()

    assert status in goal.status_updates, "Status update not found in goal status updates"

    # Refresh the goal object after commit
    context.session.refresh(goal)

    logging.info(f"Status updates after commit and refresh: {goal.status_updates}")

    assert goal.id

    upsert_embedding(context.session, goal)

    if not goal.is_active:
        from elroy.tools.messenger import remove_goal_from_context

        remove_goal_from_context(context, goal.id)


def get_active_goals_summary(context: ElroyContext) -> str:
    """
    Retrieve a summary of active goals for a given user.

    Args:
        session (Session): The database session.
        user_id (int): The ID of the user.

    Returns:
        str: A formatted string summarizing the active goals.
    """
    return pipe(
        get_active_goals(context),
        map(str),
        list,
        "\n\n".join,
    )  # type: ignore


def get_active_goals(context: ElroyContext) -> List[Goal]:
    """
    Retrieve active goals for a given user.

    Args:
        session (Session): The database session.
        user_id (int): The ID of the user.

    Returns:
        List[Goal]: A list of active goals.
    """
    return context.session.exec(
        select(Goal)
        .where(
            Goal.user_id == context.user_id,
            Goal.is_active == True,
        )
        .order_by(Goal.priority)  # type: ignore
    ).all()


def get_goal_facts(context: ElroyContext) -> List[Fact]:
    """
    Retrieve goal-related facts for a given user after a specific epoch time.

    Args:
        session (Session): The database session.
        user_id (int): The ID of the user.
        after_epoch_utc_seconds (int): The epoch time in UTC seconds.

    Returns:
        List[Fact]: A list of goal-related facts.
    """
    return pipe(
        context.session.exec(select(Goal).where(Goal.user_id == context.user_id)).all(),
        map(lambda _: _.to_fact()),
        list,
    )  # type: ignore


def get_goal_internal_monologue(last_user_message: str, goal: str) -> str:
    from elroy.llm.prompts import CHAT_MODEL, query_llm_short_limit

    return (
        query_llm_short_limit(
            prompt="LAST USER MESSAGE" + last_user_message + "\n" + "GOAL: " + goal,
            model=CHAT_MODEL,
            system="You are the internal monologue of an AI assistant. You will be given a user message, and a goal that has been recalled from memory."
            "Formulate a short internal monologue thought process that the AI might have when deciding how to respond to the user message in the context of the goal.",
        )
        + f" I may be able to use my tools {mark_goal_completed.__name__} or {add_goal_status_update.__name__} to help track this goal."
    )
