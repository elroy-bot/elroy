from datetime import timedelta

import pytest

from elroy.core.ctx import ElroyContext
from elroy.repository.reminders.operations import do_create_due_item
from elroy.repository.reminders.queries import (
    get_due_item_by_name,
    get_due_item_context_msgs,
    get_due_timed_items,
)
from elroy.repository.reminders.tools import delete_due_item
from elroy.utils.clock import utc_now
from tests.utils import (
    MockCliIO,
    create_due_item_in_past,
    get_active_due_items_summary,
    process_test_message,
    quiz_assistant_bool,
)


@pytest.mark.flaky(reruns=3)
def test_create_timed_due_item(ctx: ElroyContext):
    """Test creating a timed due item through assistant interaction."""
    quiz_assistant_bool(False, ctx, "Do I have any reminders about taking medicine?")

    tomorrow = (utc_now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    process_test_message(
        ctx,
        f"Create a reminder for me: 'Take medicine' at {tomorrow}. Please create the reminder without any clarifying questions.",
    )

    assert "medicine" in get_active_due_items_summary(ctx).lower(), "Medicine due item not found in active due items."
    quiz_assistant_bool(True, ctx, "Do I have any reminders about taking medicine?")


@pytest.mark.flaky(reruns=3)
def test_create_contextual_due_item(ctx: ElroyContext):
    """Test creating a contextual due item."""
    quiz_assistant_bool(False, ctx, "Do I have any reminders about exercise?")

    process_test_message(
        ctx,
        "Create a reminder for me: 'Do 20 push-ups' that should trigger when I mention feeling stressed. Please create the reminder without any clarifying questions.",
    )

    assert "push-ups" in get_active_due_items_summary(ctx).lower(), "Push-ups due item not found in active due items."
    quiz_assistant_bool(True, ctx, "Do I have any reminders about exercise or push-ups?")


def test_delete_due_item(ctx: ElroyContext):
    """Test deleting a due item."""
    do_create_due_item(ctx, "test_reminder", "Test reminder text", trigger_context="whenever")

    assert "test_reminder" in get_active_due_items_summary(ctx), "Test due item not created."

    process_test_message(ctx, "Please delete my reminder called 'test_reminder' without any clarifying questions.")

    quiz_assistant_bool(False, ctx, "Do I have a reminder called 'test_reminder'?")


def test_rename_due_item(ctx: ElroyContext):
    """Test renaming a due item."""
    do_create_due_item(ctx, "old_name", "Reminder to test renaming", None, "Any time")

    process_test_message(ctx, "Please rename my reminder 'old_name' to 'new_name' without any clarifying questions.")

    quiz_assistant_bool(False, ctx, "Do I have a reminder called 'old_name'?")
    quiz_assistant_bool(True, ctx, "Do I have a reminder called 'new_name'?")


def test_update_due_item_text(ctx: ElroyContext):
    """Test updating due-item text."""
    do_create_due_item(ctx, "update_test", "Original text", trigger_context="whenever")

    process_test_message(ctx, "Please update the text of my reminder 'update_test' to 'Updated text' without any clarifying questions.")

    summary = get_active_due_items_summary(ctx)
    assert "Updated text" in summary, "Due-item text was not updated."
    assert "Original text" not in summary, "Original text still present."


def test_due_item_detection(ctx: ElroyContext):
    """Test that due timed items are properly detected."""
    create_due_item_in_past(
        ctx=ctx,
        name="due_test",
        text="This reminder is due",
    )

    due_items = get_due_timed_items(ctx)
    assert len(due_items) > 0, "Due item not detected."
    assert any(item.name == "due_test" for item in due_items), "Specific due item not found."


@pytest.mark.skip(reason="TODO")
def test_due_item_context_messages(ctx: ElroyContext):
    """Test that due items generate proper context messages."""
    create_due_item_in_past(
        ctx=ctx,
        name="context_msg_test",
        text="This generates context message",
    )

    context_msgs = get_due_item_context_msgs(ctx)

    assert len(context_msgs) > 0, "No context messages generated for due item."

    msg_content = context_msgs[-1].content
    assert "⏰ DUE ITEM" in msg_content, "Context message missing due-item indicator."  # type: ignore[arg-type]
    assert "context_msg_test" in msg_content, "Context message missing item name."  # type: ignore[arg-type]
    assert "This generates context message" in msg_content, "Context message missing item text."  # type: ignore[arg-type]
    assert "delete_due_item" in msg_content, "Context message missing instruction to delete."  # type: ignore[arg-type]


def test_future_due_item_not_due(ctx: ElroyContext):
    """Test that future due items are not considered due."""
    future_time = utc_now() + timedelta(days=1)
    do_create_due_item(
        ctx=ctx,
        name="future_test",
        text="This reminder is for tomorrow",
        trigger_time=future_time,
    )

    due_items = get_due_timed_items(ctx)
    assert not any(item.name == "future_test" for item in due_items), "Future due item incorrectly marked as due."

    context_msgs = get_due_item_context_msgs(ctx)
    assert not any("future_test" in msg.content for msg in context_msgs), "Context message generated for future due item."  # type: ignore


def test_contextual_due_item_not_due(ctx: ElroyContext):
    """Test that contextual-only due items are not considered due by time."""
    do_create_due_item(
        ctx=ctx,
        name="contextual_test",
        text="Context-only reminder",
        trigger_context="when user mentions work",
    )

    due_items = get_due_timed_items(ctx)
    assert not any(item.name == "contextual_test" for item in due_items), "Contextual due item incorrectly in due-timed items."


def test_duplicate_due_item_name(io: MockCliIO, ctx: ElroyContext):
    """Test that creating a due item with duplicate name is handled properly."""
    do_create_due_item(ctx, "duplicate_test", "First reminder", trigger_context="whenever")

    process_test_message(
        ctx, "Create a reminder called 'duplicate_test' with text 'Second reminder'. Please create without clarifying questions."
    )

    quiz_assistant_bool(True, ctx, "Did the reminder I asked you to create already exist with that name?")


def test_nonexistent_due_item_operations(io: MockCliIO, ctx: ElroyContext):
    """Test operations on non-existent due items."""
    process_test_message(ctx, "Please delete my reminder called 'nonexistent_reminder'.")

    quiz_assistant_bool(False, ctx, "Did the reminder I asked you to delete exist?")


@pytest.mark.flaky(reruns=3)
def test_due_item_integration_workflow(ctx: ElroyContext):
    """Test a complete workflow of due-item operations."""
    quiz_assistant_bool(False, ctx, "Do I have any reminders about appointments?")

    tomorrow = (utc_now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    process_test_message(ctx, f"Create a reminder: 'Doctor appointment' for {tomorrow}. Please create without questions.")

    assert "doctor appointment" in get_active_due_items_summary(ctx).lower()
    quiz_assistant_bool(True, ctx, "Do I have any reminders about appointments?")

    process_test_message(
        ctx, "Update my 'Doctor appointment' reminder text to 'Doctor appointment - bring insurance card'. Please update without questions."
    )

    summary = get_active_due_items_summary(ctx).lower()
    assert "insurance card" in summary

    process_test_message(ctx, "Rename my 'Doctor appointment' reminder to 'Medical checkup'. Please rename without questions.")

    quiz_assistant_bool(False, ctx, "Do I have a reminder called 'Doctor appointment'?")
    quiz_assistant_bool(True, ctx, "Do I have a reminder called 'Medical checkup'?")

    process_test_message(ctx, "Delete my 'Medical checkup' reminder. Please delete without questions.")

    quiz_assistant_bool(False, ctx, "Do I have any reminders about medical or checkup?")


@pytest.mark.skip("TODO")
def test_due_item_deactivation_sets_is_active_to_none(ctx: ElroyContext):
    """Test that due-item deactivation sets is_active to None (not False) for unique constraint."""
    due_item = do_create_due_item(
        ctx=ctx,
        name="deactivation_test",
        text="Test deactivation",
    )
    original_id = due_item.id

    delete_due_item(ctx, "deactivation_test")

    assert get_due_item_by_name(ctx, "deactivation_test") is None, "Due item should not be returned since it should be inactive"

    new_due_item = do_create_due_item(
        ctx=ctx,
        name="deactivation_test",
        text="New due item with same name",
    )

    assert new_due_item.id != original_id, "New due item should have different ID"
    assert new_due_item.is_active is True, "New due item should be active"
