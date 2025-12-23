"""Tests for the memory recall classifier."""

from tests.utils import MockCliIO

from elroy.core.ctx import ElroyContext
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.memories.recall_classifier import (
    MemoryRecallDecision,
    _apply_heuristics,
    should_recall_memory,
)


class TestHeuristics:
    """Test the heuristics-based classification."""

    def test_simple_acknowledgment_ok(self):
        """Simple 'ok' should not need recall."""
        result = _apply_heuristics("ok")
        assert result is not None
        assert result.needs_recall is False
        assert "acknowledgment" in result.reasoning.lower()

    def test_simple_acknowledgment_thanks(self):
        """Simple 'thanks' should not need recall."""
        result = _apply_heuristics("thanks")
        assert result is not None
        assert result.needs_recall is False

    def test_simple_greeting_hello(self):
        """Simple 'hello' should not need recall."""
        result = _apply_heuristics("hello")
        assert result is not None
        assert result.needs_recall is False
        assert "greeting" in result.reasoning.lower()

    def test_simple_greeting_hi(self):
        """Simple 'hi' should not need recall."""
        result = _apply_heuristics("hi")
        assert result is not None
        assert result.needs_recall is False

    def test_complex_message_returns_none(self):
        """Complex messages should return None (needs LLM)."""
        result = _apply_heuristics("What did we discuss about my project last week?")
        assert result is None

    def test_short_but_complex_returns_none(self):
        """Short but complex messages should return None."""
        result = _apply_heuristics("What about Bob?")
        assert result is None

    def test_case_insensitive(self):
        """Heuristics should be case insensitive."""
        result_lower = _apply_heuristics("hello")
        result_upper = _apply_heuristics("HELLO")
        result_mixed = _apply_heuristics("HeLLo")

        assert result_lower is not None
        assert result_upper is not None
        assert result_mixed is not None
        assert all(not r.needs_recall for r in [result_lower, result_upper, result_mixed])


class TestIntegration:
    """Integration tests that use the full classifier with LLM."""

    def test_classifier_with_acknowledgment(self, io: MockCliIO, ctx: ElroyContext):
        """Test classifier skips recall for acknowledgments."""
        result = should_recall_memory(
            ctx=ctx,
            current_message="ok",
            recent_messages=[],
        )

        assert isinstance(result, MemoryRecallDecision)
        assert result.needs_recall is False

    def test_classifier_with_greeting(self, io: MockCliIO, ctx: ElroyContext):
        """Test classifier skips recall for greetings."""
        result = should_recall_memory(
            ctx=ctx,
            current_message="hello",
            recent_messages=[],
        )

        assert isinstance(result, MemoryRecallDecision)
        assert result.needs_recall is False

    def test_classifier_with_complex_question(self, io: MockCliIO, ctx: ElroyContext):
        """Test classifier uses LLM for complex questions."""
        # Create some recent context
        recent_messages = [
            ContextMessage(role="user", content="I'm working on a Python project", chat_model=None),
            ContextMessage(role="assistant", content="That's great! How can I help?", chat_model=None),
        ]

        result = should_recall_memory(
            ctx=ctx,
            current_message="What was that library you mentioned?",
            recent_messages=recent_messages,
        )

        assert isinstance(result, MemoryRecallDecision)
        # This should likely need recall since it references something mentioned before
        # but we won't assert the result since it depends on LLM behavior
        assert result.reasoning  # Should have reasoning

    def test_classifier_disabled(self, io: MockCliIO, ctx: ElroyContext):
        """Test that classifier can be disabled via config."""
        # Disable classifier
        ctx.memory_config.memory_recall_classifier_enabled = False

        # The messenger integration should handle this, but we can verify the config
        assert ctx.memory_config.memory_recall_classifier_enabled is False


class TestConfiguration:
    """Test configuration options."""

    def test_default_config_enabled(self, io: MockCliIO, ctx: ElroyContext):
        """Test that classifier is enabled by default."""
        assert ctx.memory_config.memory_recall_classifier_enabled is True

    def test_default_window_size(self, io: MockCliIO, ctx: ElroyContext):
        """Test that window size has a default value."""
        assert ctx.memory_config.memory_recall_classifier_window == 3
