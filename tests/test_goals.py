from functools import partial

from elroy.store.goals import get_active_goals_summary
from tests.utils import ask_assistant_bool, process_test_message


def test_goal(onboarded_context):
    partial(process_test_message, onboarded_context)

    answer, full_response = ask_assistant_bool(onboarded_context, "Do I have any goals about going to school?")
    assert not answer, f"Returned True: {full_response}"

    # Simulate user asking elroy to create a new goal

    process_test_message(
        onboarded_context,
        "Create a new goal for me: 'Remember to go to school today'",
    )

    # Test that the goal was created, and is accessible to the agent.
    assert "Remember to go to school today" in get_active_goals_summary(onboarded_context), "Goal not found in active goals."

    # Verify Elroy's knowledge about the new goal
    answer, full_response = ask_assistant_bool(
        onboarded_context,
        "Do I have any goals about going to school?",
    )
    assert answer, f"Returned False: {full_response}"

    # Test updating a goal.
    process_test_message(
        onboarded_context,
        "I have an update on my goal about school. I am now on my way to school. Please record a status update about my goal.",
    )

    # Verify that the goal's new status is recorded and reachable.
    answer, full_response = ask_assistant_bool(
        onboarded_context,
        "Is the status of my goal similar to, I am on my way to school?",
    )
    assert answer, f"Returned False: {full_response}"

    # Test completing a goal.
    process_test_message(
        onboarded_context,
        "I have completed my goal about school. Please mark it as completed.",
    )

    answer, full_response = ask_assistant_bool(
        onboarded_context,
        "Do I have any active goals about going to school?",
    )
    assert not answer, f"Returned True: {full_response}"
