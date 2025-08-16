"""Tests for reminder integration with the messenger system"""

from datetime import timedelta

from tests.utils import (
    MockCliIO,
    create_reminder_in_past,
    process_test_message,
    quiz_assistant_bool,
)

from elroy.core.ctx import ElroyContext
from elroy.repository.reminders.operations import do_create_reminder
from elroy.repository.reminders.queries import get_due_reminder_context_msgs
from elroy.utils.clock import utc_now


def test_due_reminder_surfaces_in_conversation(io: MockCliIO, ctx: ElroyContext):
    """Test that due reminders automatically surface in conversation"""
    # Create a reminder for 5 minutes from now
    create_reminder_in_past(ctx=ctx, name="medicine_reminder", text="Take your daily medicine")

    # Start a conversation - the due reminder should be surfaced (time is now 10 minutes ahead)
    response = process_test_message(ctx, "Hi, how are you doing today?")

    response_text = "".join(response).lower()

    # The assistant should mention the due reminder
    assert "medicine" in response_text or "reminder" in response_text, "Due reminder not surfaced in conversation"

    # Assistant should know about the reminder
    quiz_assistant_bool(True, ctx, "Did you just inform me about a reminder that was due?")


def test_multiple_due_reminders_all_surface(io: MockCliIO, ctx: ElroyContext):
    """Test that multiple due reminders all surface in conversation"""

    # Create multiple due reminders
    create_reminder_in_past(ctx=ctx, name="reminder1", text="First due reminder")
    create_reminder_in_past(ctx=ctx, name="reminder2", text="Second due reminder")

    # Get context messages - should have one for each due reminder
    context_msgs = get_due_reminder_context_msgs(ctx)
    assert len(context_msgs) >= 2, "Not all due reminders generated context messages"

    # Start conversation
    response = process_test_message(ctx, "What's on my schedule today?")

    response_text = "".join(response).lower()

    # Should mention both reminders
    assert "first due reminder" in response_text or "reminder1" in response_text, "First reminder not mentioned"
    assert "second due reminder" in response_text or "reminder2" in response_text, "Second reminder not mentioned"


def test_assistant_uses_delete_reminder_for_due_reminders(io: MockCliIO, ctx: ElroyContext):
    """Test that assistant uses delete_reminder tool when handling due reminders"""
    # Create a due reminder
    create_reminder_in_past(ctx=ctx, name="cleanup_test", text="This should be cleaned up")

    # Start a conversation where the assistant should handle the due reminder
    process_test_message(ctx, "Hello, please handle any due reminders and clean them up.")

    # The reminder should be deleted after being surfaced
    quiz_assistant_bool(False, ctx, "Do I still have an active reminder called 'cleanup_test'?")


def test_no_due_reminders_no_extra_context(io: MockCliIO, ctx: ElroyContext):
    """Test that when no reminders are due, no extra context is added"""
    # Create a future reminder (not due)
    future_time = utc_now() + timedelta(days=1)
    future_reminder = do_create_reminder(ctx=ctx, name="future_reminder", text="This is for tomorrow", trigger_time=future_time)
    # Mark it as completed for the test
    future_reminder.status = "completed"
    future_reminder.is_active = False
    ctx.db.persist(future_reminder)

    # Get context messages - should be empty for due reminders
    context_msgs = get_due_reminder_context_msgs(ctx)
    assert len(context_msgs) == 0, "Context messages generated for future reminder"

    # Normal conversation should not mention reminders
    response = process_test_message(ctx, "How's the weather today?")

    response_text = "".join(response).lower()

    # Should not automatically mention the future reminder
    assert "future_reminder" not in response_text, "Future reminder mentioned unnecessarily"


def test_hybrid_reminder_surfaces_when_time_due(io: MockCliIO, ctx: ElroyContext):
    """Test that hybrid reminders surface when their time component is due"""
    # Create a hybrid reminder that's time-due
    create_reminder_in_past(
        ctx=ctx,
        name="hybrid_test",
        text="Hybrid reminder text",
        reminder_context="when user mentions work",
    )

    # Should be detected as due
    context_msgs = get_due_reminder_context_msgs(ctx)
    assert len(context_msgs) > 0, "Hybrid reminder not detected as due"

    # Should surface in conversation
    response = process_test_message(ctx, "What's happening?")

    response_text = "".join(response).lower()
    assert "hybrid reminder text" in response_text or "hybrid_test" in response_text, "Hybrid reminder not surfaced"
