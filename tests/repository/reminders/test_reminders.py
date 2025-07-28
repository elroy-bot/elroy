from datetime import timedelta

import pytest
from tests.utils import (
    MockCliIO,
    get_active_reminders_summary,
    process_test_message,
    quiz_assistant_bool,
)

from elroy.core.constants import SYSTEM
from elroy.core.ctx import ElroyContext
from elroy.db.db_models import Reminder
from elroy.repository.context_messages.queries import get_context_messages
from elroy.repository.recall.queries import is_in_context
from elroy.repository.reminders.operations import do_create_reminder
from elroy.repository.reminders.queries import (
    get_due_reminder_context_msgs,
    get_due_timed_reminders,
    get_reminder_by_name,
)
from elroy.repository.reminders.tools import (
    deactivate_reminder,
)
from elroy.utils.clock import utc_now


def test_create_timed_reminder(ctx: ElroyContext):
    """Test creating a timed reminder through assistant interaction"""
    # Test that no reminders exist initially
    quiz_assistant_bool(False, ctx, "Do I have any reminders about taking medicine?")

    # Create a timed reminder
    tomorrow = (utc_now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    process_test_message(
        ctx, f"Create a reminder for me: 'Take medicine' at {tomorrow}. Please create the reminder without any clarifying questions."
    )

    # Verify the reminder was created
    assert "medicine" in get_active_reminders_summary(ctx).lower(), "Medicine reminder not found in active reminders."

    # Verify assistant knows about the reminder
    quiz_assistant_bool(True, ctx, "Do I have any reminders about taking medicine?")


def test_create_contextual_reminder(ctx: ElroyContext):
    """Test creating a contextual reminder"""
    # Test that no reminders exist initially
    quiz_assistant_bool(False, ctx, "Do I have any reminders about exercise?")

    # Create a contextual reminder
    process_test_message(
        ctx,
        "Create a reminder for me: 'Do 20 push-ups' that should trigger when I mention feeling stressed. Please create the reminder without any clarifying questions.",
    )

    # Verify the reminder was created
    assert "push-ups" in get_active_reminders_summary(ctx).lower(), "Push-ups reminder not found in active reminders."

    # Verify assistant knows about the reminder
    quiz_assistant_bool(True, ctx, "Do I have any reminders about exercise or push-ups?")


def test_create_hybrid_reminder(ctx: ElroyContext):
    """Test creating a reminder with both time and context triggers"""
    tomorrow = (utc_now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    process_test_message(
        ctx,
        f"Create a reminder: 'Call doctor' for {tomorrow} that also triggers when I mention back pain. Please create without clarifying questions.",
    )

    # Verify the reminder was created
    reminder_summary = get_active_reminders_summary(ctx).lower()
    assert "call doctor" in reminder_summary, "Doctor reminder not found in active reminders."
    assert "back pain" in reminder_summary, "Context not found in reminder."


def test_delete_reminder(ctx: ElroyContext):
    """Test deleting a reminder"""
    # Create a reminder first
    do_create_reminder(ctx, "test_reminder", "Test reminder text", reminder_context="whenever")

    # Verify it exists
    assert "test_reminder" in get_active_reminders_summary(ctx), "Test reminder not created."

    # Delete the reminder through assistant
    process_test_message(ctx, "Please delete my reminder called 'test_reminder' without any clarifying questions.")

    # Verify it's gone
    quiz_assistant_bool(False, ctx, "Do I have a reminder called 'test_reminder'?")


def test_rename_reminder(ctx: ElroyContext):
    """Test renaming a reminder"""
    # Create a reminder first
    do_create_reminder(ctx, "old_name", "Reminder to test renaming")

    # Rename through assistant
    process_test_message(ctx, "Please rename my reminder 'old_name' to 'new_name' without any clarifying questions.")

    # Verify the rename worked
    quiz_assistant_bool(False, ctx, "Do I have a reminder called 'old_name'?")
    quiz_assistant_bool(True, ctx, "Do I have a reminder called 'new_name'?")


def test_update_reminder_text(ctx: ElroyContext):
    """Test updating reminder text"""
    # Create a reminder first
    do_create_reminder(ctx, "update_test", "Original text", reminder_context="whenever")

    # Update text through assistant
    process_test_message(ctx, "Please update the text of my reminder 'update_test' to 'Updated text' without any clarifying questions.")

    # Verify the text was updated
    reminder_summary = get_active_reminders_summary(ctx)
    assert "Updated text" in reminder_summary, "Reminder text was not updated."
    assert "Original text" not in reminder_summary, "Original text still present."


def test_print_reminder(ctx: ElroyContext):
    """Test printing reminder details"""
    # Create a reminder with specific details
    tomorrow = utc_now() + timedelta(days=1)
    do_create_reminder(
        ctx,
        "detailed_reminder",
        "Take vitamins",
        trigger_time=tomorrow,
        reminder_context="when I mention health",
    )

    # Print the reminder through assistant
    response = process_test_message(ctx, "Please show me the details of my reminder 'detailed_reminder'.")

    # Verify details are shown
    response_text = "".join(response).lower()
    assert "take vitamins" in response_text, "Reminder text not shown."
    assert "health" in response_text, "Context not shown."


def test_reminder_in_context_when_active(io: MockCliIO, ctx: ElroyContext):
    """Test that reminders appear in context when active"""
    # Create a reminder directly
    reminder = ctx.db.persist(Reminder(user_id=ctx.user_id, name="context_test", text="Test reminder in context", is_active=True))

    # Check if it's in context
    assert is_in_context(get_context_messages(ctx), reminder), "Active reminder should be in context."

    # Delete the reminder
    deactivate_reminder(ctx, "context_test")

    # Refresh and check it's no longer in context
    ctx.db.refresh(reminder)
    assert not is_in_context(get_context_messages(ctx), reminder), "Deleted reminder should not be in context."


def test_due_reminder_detection(ctx: ElroyContext):
    """Test that due timed reminders are properly detected"""
    # Create a reminder that's already due
    past_time = utc_now() - timedelta(minutes=5)
    due_reminder = Reminder(user_id=ctx.user_id, name="due_test", text="This reminder is due", trigger_datetime=past_time, is_active=True)
    ctx.db.add(due_reminder)
    ctx.db.commit()

    # Check that it's detected as due
    due_reminders = get_due_timed_reminders(ctx)
    assert len(due_reminders) > 0, "Due reminder not detected."
    assert any(r.name == "due_test" for r in due_reminders), "Specific due reminder not found."


def test_due_reminder_context_messages(ctx: ElroyContext):
    """Test that due reminders generate proper context messages"""
    # Create a reminder that's already due
    past_time = utc_now() - timedelta(minutes=5)
    due_reminder = Reminder(
        user_id=ctx.user_id, name="context_msg_test", text="This generates context message", trigger_datetime=past_time, is_active=True
    )
    ctx.db.add(due_reminder)
    ctx.db.commit()

    # Get context messages for due reminders
    context_msgs = get_due_reminder_context_msgs(ctx)

    assert len(context_msgs) > 0, "No context messages generated for due reminder."

    # Check message content
    msg_content = context_msgs[0].content
    assert "⏰ REMINDER DUE" in msg_content, "Context message missing reminder due indicator."  # type: ignore
    assert "context_msg_test" in msg_content, "Context message missing reminder name."  # type: ignore
    assert "This generates context message" in msg_content, "Context message missing reminder text."  # type: ignore
    assert "delete_reminder" in msg_content, "Context message missing instruction to delete."  # type: ignore
    assert context_msgs[0].role == SYSTEM, "Context message should be from system."


def test_future_reminder_not_due(ctx: ElroyContext):
    """Test that future reminders are not considered due"""
    # Create a reminder for tomorrow
    future_time = utc_now() + timedelta(days=1)
    future_reminder = Reminder(
        user_id=ctx.user_id, name="future_test", text="This reminder is for tomorrow", trigger_datetime=future_time, is_active=True
    )
    ctx.db.add(future_reminder)
    ctx.db.commit()

    # Check that it's not considered due
    due_reminders = get_due_timed_reminders(ctx)
    assert not any(r.name == "future_test" for r in due_reminders), "Future reminder incorrectly marked as due."

    # Check no context messages are generated
    context_msgs = get_due_reminder_context_msgs(ctx)
    assert not any("future_test" in msg.content for msg in context_msgs), "Context message generated for future reminder."  # type: ignore


def test_contextual_reminder_not_due(ctx: ElroyContext):
    """Test that contextual-only reminders are not considered due by time"""
    # Create a contextual reminder
    contextual_reminder = Reminder(
        user_id=ctx.user_id,
        name="contextual_test",
        text="Context-only reminder",
        reminder_context="when user mentions work",
        is_active=True,
    )
    ctx.db.add(contextual_reminder)
    ctx.db.commit()

    # Check that it's not in due timed reminders
    due_reminders = get_due_timed_reminders(ctx)
    assert not any(r.name == "contextual_test" for r in due_reminders), "Contextual reminder incorrectly in due timed reminders."


def test_duplicate_reminder_name(io: MockCliIO, ctx: ElroyContext):
    """Test that creating a reminder with duplicate name is handled properly"""
    # Create first reminder
    do_create_reminder(ctx, "duplicate_test", "First reminder", reminder_context="whenever")

    # Try to create another with same name
    process_test_message(
        ctx, "Create a reminder called 'duplicate_test' with text 'Second reminder'. Please create without clarifying questions."
    )

    # Should inform about existing reminder
    quiz_assistant_bool(True, ctx, "Did the reminder I asked you to create already exist with that name?")


def test_nonexistent_reminder_operations(io: MockCliIO, ctx: ElroyContext):
    """Test operations on non-existent reminders"""
    # Try to delete non-existent reminder
    process_test_message(ctx, "Please delete my reminder called 'nonexistent_reminder'.")

    # Should inform that reminder doesn't exist
    quiz_assistant_bool(False, ctx, "Did the reminder I asked you to delete exist?")


@pytest.mark.flaky(reruns=3)
def test_reminder_integration_workflow(ctx: ElroyContext):
    """Test a complete workflow of reminder operations"""
    # Start with no reminders
    quiz_assistant_bool(False, ctx, "Do I have any reminders about appointments?")

    # Create a reminder
    tomorrow = (utc_now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    process_test_message(ctx, f"Create a reminder: 'Doctor appointment' for {tomorrow}. Please create without questions.")

    # Verify creation
    assert "doctor appointment" in get_active_reminders_summary(ctx).lower()
    quiz_assistant_bool(True, ctx, "Do I have any reminders about appointments?")

    # Update the reminder text
    process_test_message(
        ctx, "Update my 'Doctor appointment' reminder text to 'Doctor appointment - bring insurance card'. Please update without questions."
    )

    # Verify update
    reminder_summary = get_active_reminders_summary(ctx).lower()
    assert "insurance card" in reminder_summary

    # Rename the reminder
    process_test_message(ctx, "Rename my 'Doctor appointment' reminder to 'Medical checkup'. Please rename without questions.")

    # Verify rename
    quiz_assistant_bool(False, ctx, "Do I have a reminder called 'Doctor appointment'?")
    quiz_assistant_bool(True, ctx, "Do I have a reminder called 'Medical checkup'?")

    # Delete the reminder
    process_test_message(ctx, "Delete my 'Medical checkup' reminder. Please delete without questions.")

    # Verify deletion
    quiz_assistant_bool(False, ctx, "Do I have any reminders about medical or checkup?")


def test_reminder_deactivation_sets_is_active_to_none(ctx: ElroyContext):
    """Test that reminder deactivation sets is_active to None (not False) for unique constraint"""
    # Create a reminder
    reminder = Reminder(user_id=ctx.user_id, name="deactivation_test", text="Test deactivation", is_active=True)
    ctx.db.add(reminder)
    ctx.db.commit()
    original_id = reminder.id

    # Delete the reminder
    deactivate_reminder(ctx, "deactivation_test")

    # Refresh and check is_active is None, not False
    assert get_reminder_by_name(ctx, "deactivation_test") is None, "Reminder should not be returned since it should be inactive"

    # Should be able to create a new reminder with the same name
    new_reminder = Reminder(user_id=ctx.user_id, name="deactivation_test", text="New reminder with same name", is_active=True)
    ctx.db.add(new_reminder)
    ctx.db.commit()

    # Should succeed because old reminder has is_active=None
    assert new_reminder.id != original_id, "New reminder should have different ID"
    assert new_reminder.is_active is True, "New reminder should be active"
