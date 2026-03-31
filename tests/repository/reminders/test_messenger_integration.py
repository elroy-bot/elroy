"""Tests for due-item integration with the messenger system."""

from datetime import timedelta

from elroy.core.ctx import ElroyContext
from elroy.repository.reminders.operations import do_create_due_item
from elroy.repository.reminders.queries import get_due_item_context_msgs
from elroy.utils.clock import utc_now
from tests.utils import (
    MockCliIO,
    create_due_item_in_past,
    process_test_message,
    quiz_assistant_bool,
)


def test_due_item_surfaces_in_conversation(io: MockCliIO, ctx: ElroyContext):
    """Test that due items automatically surface in conversation."""
    create_due_item_in_past(ctx=ctx, name="medicine_reminder", text="Take your daily medicine")

    response = process_test_message(ctx, "Hi, how are you doing today?")
    response_text = "".join(response).lower()

    assert "medicine" in response_text or "due item" in response_text, "Due item not surfaced in conversation"
    quiz_assistant_bool(True, ctx, "Did you just inform me about a reminder that was due?")


def test_multiple_due_items_all_surface(io: MockCliIO, ctx: ElroyContext):
    """Test that multiple due items all surface in conversation."""
    create_due_item_in_past(ctx=ctx, name="reminder1", text="First due reminder")
    create_due_item_in_past(ctx=ctx, name="reminder2", text="Second due reminder")

    context_msgs = get_due_item_context_msgs(ctx)
    assert len(context_msgs) >= 2, "Not all due items generated context messages"

    response = process_test_message(ctx, "What's on my schedule today?")
    response_text = "".join(response).lower()

    assert "first due reminder" in response_text or "reminder1" in response_text, "First due item not mentioned"
    assert "second due reminder" in response_text or "reminder2" in response_text, "Second due item not mentioned"


def test_assistant_uses_delete_due_item_for_due_items(io: MockCliIO, ctx: ElroyContext):
    """Test that assistant uses delete_due_item when handling due items."""
    create_due_item_in_past(ctx=ctx, name="cleanup_test", text="This should be cleaned up")

    process_test_message(ctx, "Hello, please handle any due reminders and clean them up.")

    quiz_assistant_bool(False, ctx, "Do I still have an active reminder called 'cleanup_test'?")


def test_no_due_items_no_extra_context(io: MockCliIO, ctx: ElroyContext):
    """Test that when no due items are due, no extra context is added."""
    future_time = utc_now() + timedelta(days=1)
    future_due_item = do_create_due_item(ctx=ctx, name="future_reminder", text="This is for tomorrow", trigger_time=future_time)
    future_due_item.status = "completed"
    future_due_item.is_active = False
    ctx.db.persist(future_due_item)

    context_msgs = get_due_item_context_msgs(ctx)
    assert len(context_msgs) == 0, "Context messages generated for future due item"

    response = process_test_message(ctx, "How's the weather today?")
    response_text = "".join(response).lower()

    assert "future_reminder" not in response_text, "Future due item mentioned unnecessarily"


def test_hybrid_due_item_surfaces_when_time_due(io: MockCliIO, ctx: ElroyContext):
    """Test that hybrid due items surface when their time component is due."""
    create_due_item_in_past(
        ctx=ctx,
        name="hybrid_test",
        text="Hybrid reminder text",
        trigger_context="when user mentions work",
    )

    context_msgs = get_due_item_context_msgs(ctx)
    assert len(context_msgs) > 0, "Hybrid due item not detected as due"

    response = process_test_message(ctx, "What's happening?")
    response_text = "".join(response).lower()
    assert "hybrid reminder text" in response_text or "hybrid_test" in response_text, "Hybrid due item not surfaced"
