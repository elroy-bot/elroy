import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlmodel import Session, select
from toolz import first, pipe
from toolz.curried import filter, map

from elroy.store.data_models import Fact, Goal, convert_to_utc
from elroy.store.embeddings import upsert_embedding
from elroy.system.clock import get_utc_now, string_to_timedelta
from elroy.system.parameters import GOAL_CHECKIN_COUNT


def get_goals_with_due_status(session: Session, user_id: int) -> List[Goal]:
    """
    Retrieve goals with due status for a given user.

    Args:
        session (Session): The database session.
        user_id (int): The ID of the user.

    Returns:
        List[Goal]: A list of goals with due status.
    """
    goals = session.exec(select(Goal).where(Goal.user_id == user_id, Goal.is_active == True)).all()

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
    session: Session,
    user_id: int,
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
    existing_goal = session.exec(select(Goal).where(Goal.user_id == user_id, Goal.name == goal_name, Goal.is_active == True)).one_or_none()
    if existing_goal:
        raise Exception(f"Active goal {goal_name} already exists for user {user_id}")
    else:
        goal = Goal(
            user_id=user_id,
            name=goal_name,
            description=description,
            strategy=strategy,
            end_condition=end_condition,
            priority=priority,
            target_completion_time=get_utc_now() + string_to_timedelta(time_to_completion) if time_to_completion else None,
        )
        session.add(goal)
        session.commit()
        session.refresh(goal)

        upsert_embedding(session, goal)


def create_onboarding_goal(session: Session, user_id: int) -> None:
    from elroy.store.user import assistant_writable_user_preference_fields

    create_goal(
        session=session,
        user_id=user_id,
        goal_name="Learn basic details about user",
        description="Learn basic details about the user. This critically includes the name they wish to be called by, but should also include their relative time zone, basic biographical information, occupational details. User functions to update the information.",
        strategy="Work in questions about the user into the conversation. Use the user's name when addressing them. Ask about their time zone, and other relevant details. Do not be pushy, if the user does not wish to share the information, do not press for it.",
        end_condition=f"The following fields about the user are collected: " + ", ".join(assistant_writable_user_preference_fields),
        priority=1,
        time_to_completion="1 HOUR",
    )

    create_goal(
        session=session,
        user_id=user_id,
        goal_name="Tell user about my ability to track goals",
        description="Tell the user about my capability to track goals. Note that the goals can be automatically created and automatically brought into the converation when relevant.",
        strategy="After exchanging some pleasantries, tell the user about my ability to form long term memories, including goals",
        end_condition=f"The user has been informed about my ability to track goals",
        priority=1,
        time_to_completion="1 HOUR",
    )


def update_goal_status(session: Session, user_id: int, goal_name: str, status: str) -> None:
    """Updates a goal with the given status. If the goal is terminal, it will be marked completed and/or inactive.

    Args:
        session (Session): The database session.
        user_id (int): The user id
        goal_name (str): Name of the goal
        status (str): A brief description of what has happened with the goal so far. Limit to 100 words.
    """
    logging.info(f"Updating goal {goal_name} for user {user_id}")
    _update_goal_status(session, user_id, goal_name, status, False)


def mark_goal_completed(session: Session, user_id: int, goal_name: str, closing_comments: str) -> None:
    """Marks a goal as completed, with closing comments.

    Args:
        session (Session): The database session.
        user_id (int): The user ID
        goal_name (str): The name of the goal
        closing_comments (str): Updated status with a short account of how the goal was completed and what was learned.
    """
    _update_goal_status(
        session,
        user_id,
        goal_name,
        closing_comments,
        True,
    )


def _update_goal_status(session: Session, user_id: int, goal_name: str, status: str, is_terminal: bool) -> None:
    goal = session.exec(select(Goal).where(Goal.user_id == user_id, Goal.name == goal_name, Goal.is_active == True)).first()
    if not goal:
        raise Exception(f"Active goal {goal_name} not found for user {user_id}")

    # Append the new status update to the list
    goal.status_updates.append(status)

    # Update the goal's active status if it's terminal
    if is_terminal:
        goal.is_active = False

    goal.updated_at = get_utc_now()
    session.commit()
    session.refresh(goal)

    upsert_embedding(session, goal)


def get_active_goals_summary(session: Session, user_id: int) -> str:
    """
    Retrieve a summary of active goals for a given user.

    Args:
        session (Session): The database session.
        user_id (int): The ID of the user.

    Returns:
        str: A formatted string summarizing the active goals.
    """
    return pipe(
        get_active_goals(session, user_id),
        map(str),
        list,
        "\n\n".join,
    )  # type: ignore


def get_active_goals(session: Session, user_id: int) -> List[Goal]:
    """
    Retrieve active goals for a given user.

    Args:
        session (Session): The database session.
        user_id (int): The ID of the user.

    Returns:
        List[Goal]: A list of active goals.
    """
    return session.exec(select(Goal).where(Goal.user_id == user_id, Goal.is_active == True).order_by(Goal.priority)).all()  # type: ignore


def get_goal_facts(session: Session, user_id: int) -> List[Fact]:
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
        session.exec(select(Goal).where(Goal.user_id == user_id)).all(),
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
        + f" I may be able to use my tools {mark_goal_completed.__name__} or {update_goal_status.__name__} to help track this goal."
    )
