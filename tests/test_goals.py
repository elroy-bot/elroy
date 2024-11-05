from tests.utils import ask_assistant_bool, process_test_message

from elroy.repository.goals.queries import get_active_goals_summary


def test_goal(onboarded_context):
    answer, full_response = ask_assistant_bool(onboarded_context, "Do I have any goals about becoming president of the United States?")
    assert not answer, f"Returned True: {full_response}"

    # Simulate user asking elroy to create a new goal

    process_test_message(
        onboarded_context,
        "Create a new goal for me: 'Become my school's class president.' I will get to my goal by being nice to everyone and making flyers.",
    )

    # Test that the goal was created, and is accessible to the agent.
    assert "Become my school's class president" in get_active_goals_summary(onboarded_context), "Goal not found in active goals."

    # Verify Elroy's knowledge about the new goal
    answer, full_response = ask_assistant_bool(
        onboarded_context,
        "Do I have any goals about going to running for an election?",
    )
    assert answer, f"Expected True but got False: {full_response}"

    # Test updating a goal.
    process_test_message(
        onboarded_context,
        "I have an update about my campaign. I've put up flyers around the school.",
    )

    # Verify that the goal's new status is recorded and reachable.
    answer, full_response = ask_assistant_bool(
        onboarded_context,
        "Is the status up my update similar to: I've put up flyers around the school?",
    )
    assert answer, f"Returned False: {full_response}"

    # Test completing a goal.
    process_test_message(
        onboarded_context,
        "Great news, I won my election! My goal is now done.",
    )

    answer, full_response = ask_assistant_bool(
        onboarded_context,
        "Do I have any active goals about running for class president?",
    )
    assert not answer, f"Returned True: {full_response}"
