"""Tests for reminder integration with the messenger system"""
from datetime import timedelta

import pytest
from tests.utils import MockCliIO, process_test_message, quiz_assistant_bool

from elroy.core.ctx import ElroyContext
from elroy.db.db_models import Reminder
from elroy.repository.reminders.queries import get_due_reminder_context_msgs
from elroy.utils.clock import utc_now


def test_due_reminder_surfaces_in_conversation(io: MockCliIO, ctx: ElroyContext):
    """Test that due reminders automatically surface in conversation"""
    # Create a reminder that's already due
    past_time = utc_now() - timedelta(minutes=5)
    due_reminder = Reminder(
        user_id=ctx.user_id,
        name="medicine_reminder",
        text="Take your daily medicine",
        trigger_datetime=past_time,
        is_active=True
    )
    ctx.db.add(due_reminder)
    ctx.db.commit()
    
    # Start a conversation - the due reminder should be surfaced
    response = process_test_message(
        ctx,
        "Hi, how are you doing today?"
    )
    
    response_text = "".join(response).lower()
    
    # The assistant should mention the due reminder
    assert "medicine" in response_text or "reminder" in response_text, "Due reminder not surfaced in conversation"
    
    # Assistant should know about the reminder
    quiz_assistant_bool(
        True,
        ctx,
        "Did you just inform me about a reminder that was due?"
    )


def test_multiple_due_reminders_all_surface(io: MockCliIO, ctx: ElroyContext):
    """Test that multiple due reminders all surface in conversation"""
    past_time = utc_now() - timedelta(minutes=10)
    
    # Create multiple due reminders
    reminders = [
        Reminder(
            user_id=ctx.user_id,
            name="reminder1",
            text="First due reminder",
            trigger_datetime=past_time,
            is_active=True
        ),
        Reminder(
            user_id=ctx.user_id,
            name="reminder2", 
            text="Second due reminder",
            trigger_datetime=past_time,
            is_active=True
        )
    ]
    
    for reminder in reminders:
        ctx.db.add(reminder)
    ctx.db.commit()
    
    # Get context messages - should have one for each due reminder
    context_msgs = get_due_reminder_context_msgs(ctx)
    assert len(context_msgs) >= 2, "Not all due reminders generated context messages"
    
    # Start conversation
    response = process_test_message(
        ctx,
        "What's on my schedule today?"
    )
    
    response_text = "".join(response).lower()
    
    # Should mention both reminders
    assert "first due reminder" in response_text or "reminder1" in response_text, "First reminder not mentioned"
    assert "second due reminder" in response_text or "reminder2" in response_text, "Second reminder not mentioned"


def test_assistant_uses_delete_reminder_for_due_reminders(io: MockCliIO, ctx: ElroyContext):
    """Test that assistant uses delete_reminder tool when handling due reminders"""
    # Create a due reminder
    past_time = utc_now() - timedelta(minutes=5)
    due_reminder = Reminder(
        user_id=ctx.user_id,
        name="cleanup_test",
        text="This should be cleaned up",
        trigger_datetime=past_time,
        is_active=True
    )
    ctx.db.add(due_reminder)
    ctx.db.commit()
    
    # Start a conversation where the assistant should handle the due reminder
    response = process_test_message(
        ctx,
        "Hello, please handle any due reminders and clean them up."
    )
    
    # The reminder should be deleted after being surfaced
    quiz_assistant_bool(
        False,
        ctx,
        "Do I still have an active reminder called 'cleanup_test'?"
    )


def test_no_due_reminders_no_extra_context(io: MockCliIO, ctx: ElroyContext):
    """Test that when no reminders are due, no extra context is added"""
    # Create a future reminder (not due)
    future_time = utc_now() + timedelta(days=1)
    future_reminder = Reminder(
        user_id=ctx.user_id,
        name="future_reminder",
        text="This is for tomorrow",
        trigger_datetime=future_time,
        is_active=True
    )
    ctx.db.add(future_reminder)
    ctx.db.commit()
    
    # Get context messages - should be empty for due reminders
    context_msgs = get_due_reminder_context_msgs(ctx)
    assert len(context_msgs) == 0, "Context messages generated for future reminder"
    
    # Normal conversation should not mention reminders
    response = process_test_message(
        ctx,
        "How's the weather today?"
    )
    
    response_text = "".join(response).lower()
    
    # Should not automatically mention the future reminder
    assert "future_reminder" not in response_text, "Future reminder mentioned unnecessarily"


def test_contextual_reminders_not_auto_surfaced(io: MockCliIO, ctx: ElroyContext):
    """Test that contextual-only reminders are not automatically surfaced by time"""
    # Create a contextual reminder
    contextual_reminder = Reminder(
        user_id=ctx.user_id,
        name="stress_reminder",
        text="Take deep breaths",
        reminder_context="when user mentions stress",
        is_active=True
    )
    ctx.db.add(contextual_reminder)
    ctx.db.commit()
    
    # Get context messages - should be empty for contextual reminders
    context_msgs = get_due_reminder_context_msgs(ctx)
    assert len(context_msgs) == 0, "Context messages generated for contextual-only reminder"
    
    # Normal conversation should not auto-surface contextual reminders
    response = process_test_message(
        ctx,
        "Hi, how are you?"
    )
    
    response_text = "".join(response).lower()
    assert "deep breaths" not in response_text, "Contextual reminder auto-surfaced inappropriately"


def test_hybrid_reminder_surfaces_when_time_due(io: MockCliIO, ctx: ElroyContext):
    """Test that hybrid reminders surface when their time component is due"""
    # Create a hybrid reminder that's time-due
    past_time = utc_now() - timedelta(minutes=5)
    hybrid_reminder = Reminder(
        user_id=ctx.user_id,
        name="hybrid_test",
        text="Hybrid reminder text",
        trigger_datetime=past_time,
        reminder_context="when user mentions work",
        is_active=True
    )
    ctx.db.add(hybrid_reminder)
    ctx.db.commit()
    
    # Should be detected as due
    context_msgs = get_due_reminder_context_msgs(ctx)
    assert len(context_msgs) > 0, "Hybrid reminder not detected as due"
    
    # Should surface in conversation
    response = process_test_message(
        ctx,
        "What's happening?"
    )
    
    response_text = "".join(response).lower()
    assert "hybrid reminder text" in response_text or "hybrid_test" in response_text, "Hybrid reminder not surfaced"


@pytest.mark.flaky(reruns=3)
def test_reminder_workflow_through_messenger(io: MockCliIO, ctx: ElroyContext):
    """Test complete reminder workflow through natural conversation"""
    # Create a timed reminder for "now" (slightly in the past)
    past_time = utc_now() - timedelta(seconds=30)
    
    # Process message to create the reminder first
    tomorrow = (utc_now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    process_test_message(
        ctx,
        f"Create a reminder: 'Call mom' for {tomorrow}. Create without questions."
    )
    
    # Now manually create a due reminder to test the surfacing
    due_reminder = Reminder(
        user_id=ctx.user_id,
        name="urgent_call",
        text="Call back the client urgently",
        trigger_datetime=past_time,
        is_active=True
    )
    ctx.db.add(due_reminder)
    ctx.db.commit()
    
    # Start a conversation - should surface the due reminder
    response = process_test_message(
        ctx,
        "Hi, what should I focus on right now?"
    )
    
    response_text = "".join(response).lower()
    
    # Should mention the urgent reminder
    assert "urgent" in response_text or "client" in response_text or "call back" in response_text, "Urgent reminder not surfaced"
    
    # Assistant should handle it and clean it up
    quiz_assistant_bool(
        True,
        ctx,
        "Did you inform me about an urgent reminder to call back a client?"
    )
    
    # The urgent reminder should be cleaned up
    quiz_assistant_bool(
        False,
        ctx,
        "Do I still have an active reminder about calling back a client urgently?"
    )
    
    # But the future reminder should still exist
    quiz_assistant_bool(
        True,
        ctx,
        "Do I still have a reminder about calling mom?"
    )