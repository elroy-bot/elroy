from tests.utils import assert_false, assert_true, process_test_message

from elroy.repository.goals.queries import get_active_goals_summary


def test_goal(onboarded_context):
    assert_false(onboarded_context, "Do I have any goals about becoming president of the United States?")

    # Simulate user asking elroy to create a new goal

    process_test_message(
        onboarded_context,
        "Create a new goal for me: 'Become my school's class president.' I will get to my goal by being nice to everyone and making flyers.",
    )

    # Test that the goal was created, and is accessible to the agent.

    assert "class president" in get_active_goals_summary(onboarded_context).lower(), "Goal not found in active goals."

    # Verify Elroy's knowledge about the new goal
    assert_true(
        onboarded_context,
        "Do I have any goals about going to running for a position in student government?",
    )

    # Test updating a goal.
    process_test_message(
        onboarded_context,
        "I have an update about my campaign. I've put up flyers around the school.",
    )

    # Verify that the goal's new status is recorded and reachable.
    assert_true(
        onboarded_context,
        "Does the status update convey similar information to: I've put up flyers around the school?",
    )

    # Test completing a goal.
    process_test_message(
        onboarded_context,
        "Great news, I won my election! My goal is now done.",
    )

    assert_false(
        onboarded_context,
        "Do I have any active goals about running for class president?",
    )
