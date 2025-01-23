from tests.utils import process_test_message, quiz_assistant_bool

from elroy.cli.chat import _get_in_context_memories
from elroy.db.db_models import Goal
from elroy.repository.embeddable import is_in_context, remove_from_context
from elroy.repository.goals.operations import (
    create_goal,
    get_goal_by_name,
    mark_goal_completed,
)
from elroy.repository.goals.queries import get_active_goals_summary
from elroy.repository.message import get_context_messages
from elroy.system_commands import reset_messages


def test_assistant_goal_in_context(ctx):
    # Verify that when a goal is created by assistant, it is in context, when marked complete, it disappears
    process_test_message(ctx, "I ran a marathon today, please create a memory")

    assert any(
        "marathon" in title.lower() for title in _get_in_context_memories(ctx, get_context_messages(ctx)) if title.startswith("Memory")
    ), "Marathon memory not found in context"
    process_test_message(ctx, "Please create a new goal for me: Run a second marathon")
    assert any(
        "marathon" in title.lower() for title in _get_in_context_memories(ctx, get_context_messages(ctx)) if title.startswith("Goal")
    ), "Marathon goal not found in context"
    process_test_message(ctx, "I ran a second marathon today, please mark my goal complete")
    assert not any(
        "marathon" in title.lower() for title in _get_in_context_memories(ctx, get_context_messages(ctx)) if title.startswith("Goal")
    ), "Marathon goal still in context"


def test_goal(ctx):
    quiz_assistant_bool(False, ctx, "Do I have any goals about becoming president of the United States?")

    # Simulate user asking elroy to create a new goal

    process_test_message(
        ctx,
        "Create a new goal for me: 'Become mayor of my town.' I will get to my goal by being nice to everyone and making flyers. Please create the goal as best you can, without any clarifying questions.",
    )

    # Test that the goal was created, and is accessible to the agent.

    assert "mayor" in get_active_goals_summary(ctx).lower(), "Goal not found in active goals."

    # Verify Elroy's knowledge about the new goal
    quiz_assistant_bool(
        True,
        ctx,
        "Do I have any goals about going to running for a political office?",
    )

    # Test updating a goal.
    process_test_message(
        ctx,
        "I have an update about my campaign. I've put up flyers around my town. Please create this update as best you can without any clarifying questions",
    )

    # Verify that the goal's new status is recorded and reachable.
    quiz_assistant_bool(
        True,
        ctx,
        "Does the status update convey similar information to: I've put up flyers around my town?",
    )

    # Test completing a goal.
    process_test_message(
        ctx,
        "Great news, I won my election! My goal is now done. Please mark the goal completed, without asking any clarifying questions.",
    )

    quiz_assistant_bool(
        False,
        ctx,
        "Do I have any active goals about running for mayor of my town?",
    )


def test_goal_update_goal_slight_difference(ctx):
    create_goal(ctx, "Run 100 miles this year")
    reset_messages(ctx)

    reply = process_test_message(
        ctx,
        "I am testing function update. My goal: 'Run 100 miles in the next 365 days' has an update: I ran 4 miles today. The goal already exists. Please process a goal update.",
    )

    assert "4 miles" in get_active_goals_summary(ctx)


def test_goal_is_in_context_only_when_active(ctx):
    create_goal(ctx, "Run 100 miles this year")
    goal = get_goal_by_name(ctx, "Run 100 miles this year")
    assert isinstance(goal, Goal)
    assert is_in_context(get_context_messages(ctx), goal)

    mark_goal_completed(ctx, "Run 100 miles this year")

    ctx.db.refresh(goal)

    assert not is_in_context(get_context_messages(ctx), goal)


def test_status_update_brings_into_context(ctx):
    create_goal(ctx, "Run 100 miles this year")
    goal = get_goal_by_name(ctx, "Run 100 miles this year")
    assert goal

    remove_from_context(ctx, goal)

    assert not is_in_context(get_context_messages(ctx), goal)

    process_test_message(ctx, "I ran 4 miles today. Please update my goal: Run 100 miles this year")

    assert is_in_context(get_context_messages(ctx), goal)


def test_duplicate_goal(ctx):
    """The result should not raise an error, but should not create a duplicate goal."""
    create_goal(ctx, "Run 100 miles this year")
    remove_from_context(ctx, get_goal_by_name(ctx, "Run 100 miles this year"))  # type: ignore

    process_test_message(
        ctx,
        "Create a new goal for me: 'Run 100 miles this year.' I will get to my goal by running 10 miles a week. Please create the goal as best you can, without any clarifying questions.",
    )

    quiz_assistant_bool(True, ctx, "Did the goal I asked you to create already exist?")

    assert not ctx.io._warnings


def test_update_nonexistent_goal(ctx):
    process_test_message(ctx, "I ran 4 miles today. Please update my goal: Run 100 miles this year")
    quiz_assistant_bool(False, ctx, "Did the goal I asked you to update already exist?")

    assert not ctx.io._warnings
