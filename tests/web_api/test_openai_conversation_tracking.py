from unittest.mock import MagicMock, patch

import pytest

from elroy.core.ctx import ElroyContext
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.web_api.openai_compatible.litellm_provider import ElroyLiteLLMProvider


@pytest.fixture
def mock_ctx():
    """Create a mock ElroyContext for testing."""
    ctx = MagicMock(spec=ElroyContext)
    ctx.user_id = 1
    ctx.chat_model.name = "test-model"
    return ctx


@pytest.fixture
def provider(mock_ctx):
    """Create an ElroyLiteLLMProvider instance for testing."""
    return ElroyLiteLLMProvider(
        ctx=mock_ctx,
        enable_memory_creation=True,
        memory_creation_interval=10,
        max_memories_per_request=5,
    )


class TestOpenAIConversationTracking:
    """Tests for the conversation tracking in the OpenAI-compatible API."""

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.add_context_messages")
    def test_new_conversation(self, mock_add, mock_get_context, provider):
        """Test tracking a new conversation."""
        # Mock empty context (no existing messages)
        mock_get_context.return_value = []

        # New messages
        new_messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "Hello"}]

        # Track conversation
        provider._track_conversation(new_messages)

        # Verify all non-system messages were added
        mock_add.assert_called_once()
        added_messages = mock_add.call_args[0][1]
        assert len(added_messages) == 1
        assert added_messages[0].role == "user"
        assert added_messages[0].content == "Hello"

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.add_context_messages")
    def test_continuing_conversation(self, mock_add, mock_get_context, provider):
        """Test continuing an existing conversation."""
        # Mock existing context messages
        existing_msg1 = ContextMessage(role="system", content="You are a helpful assistant.", chat_model="test-model")
        existing_msg2 = ContextMessage(role="user", content="Hello", chat_model="test-model")
        existing_msg3 = ContextMessage(role="assistant", content="Hi there!", chat_model="test-model")
        mock_get_context.return_value = [existing_msg1, existing_msg2, existing_msg3]

        # New messages with one additional message
        new_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "What's the weather like?"},
        ]

        # Track conversation
        provider._track_conversation(new_messages)

        # Verify only the new message was added
        mock_add.assert_called_once()
        added_messages = mock_add.call_args[0][1]
        assert len(added_messages) == 1
        assert added_messages[0].role == "user"
        assert added_messages[0].content == "What's the weather like?"

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.add_context_messages")
    def test_conversation_with_divergence_at_beginning(self, mock_add, mock_get_context, provider):
        """Test conversation with divergence at the beginning."""
        # Mock existing context messages
        existing_msg1 = ContextMessage(role="system", content="You are a helpful assistant.", chat_model="test-model")
        existing_msg2 = ContextMessage(role="user", content="Hello", chat_model="test-model")
        existing_msg3 = ContextMessage(role="assistant", content="Hi there!", chat_model="test-model")
        mock_get_context.return_value = [existing_msg1, existing_msg2, existing_msg3]

        # New messages with divergence at the first user message
        new_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hi there"},  # Different from "Hello"
            {"role": "assistant", "content": "Hello! How can I help you?"},
        ]

        # Track conversation
        provider._track_conversation(new_messages)

        # Verify divergent messages were added
        mock_add.assert_called_once()
        added_messages = mock_add.call_args[0][1]
        assert len(added_messages) == 2
        assert added_messages[0].role == "user"
        assert added_messages[0].content == "Hi there"
        assert added_messages[1].role == "assistant"
        assert added_messages[1].content == "Hello! How can I help you?"

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.add_context_messages")
    def test_conversation_with_divergence_in_middle(self, mock_add, mock_get_context, provider):
        """Test conversation with divergence in the middle."""
        # Mock existing context messages
        existing_msg1 = ContextMessage(role="system", content="You are a helpful assistant.", chat_model="test-model")
        existing_msg2 = ContextMessage(role="user", content="Hello", chat_model="test-model")
        existing_msg3 = ContextMessage(role="assistant", content="Hi there!", chat_model="test-model")
        existing_msg4 = ContextMessage(role="user", content="How are you?", chat_model="test-model")
        existing_msg5 = ContextMessage(role="assistant", content="I'm doing well, thanks!", chat_model="test-model")
        mock_get_context.return_value = [existing_msg1, existing_msg2, existing_msg3, existing_msg4, existing_msg5]

        # New messages with divergence at the second user message
        new_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "What's the weather like?"},  # Different from "How are you?"
            {"role": "assistant", "content": "I don't have real-time weather data."},
        ]

        # Track conversation
        provider._track_conversation(new_messages)

        # Verify divergent messages were added
        mock_add.assert_called_once()
        added_messages = mock_add.call_args[0][1]
        assert len(added_messages) == 2
        assert added_messages[0].role == "user"
        assert added_messages[0].content == "What's the weather like?"
        assert added_messages[1].role == "assistant"
        assert added_messages[1].content == "I don't have real-time weather data."

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.add_context_messages")
    def test_conversation_with_same_messages(self, mock_add, mock_get_context, provider):
        """Test conversation with exactly the same messages."""
        # Mock existing context messages
        existing_msg1 = ContextMessage(role="system", content="You are a helpful assistant.", chat_model="test-model")
        existing_msg2 = ContextMessage(role="user", content="Hello", chat_model="test-model")
        existing_msg3 = ContextMessage(role="assistant", content="Hi there!", chat_model="test-model")
        mock_get_context.return_value = [existing_msg1, existing_msg2, existing_msg3]

        # New messages with exactly the same content
        new_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        # Track conversation
        provider._track_conversation(new_messages)

        # Verify no messages were added
        mock_add.assert_not_called()

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.add_context_messages")
    def test_conversation_with_fewer_messages(self, mock_add, mock_get_context, provider):
        """Test conversation with fewer messages than stored."""
        # Mock existing context messages
        existing_msg1 = ContextMessage(role="system", content="You are a helpful assistant.", chat_model="test-model")
        existing_msg2 = ContextMessage(role="user", content="Hello", chat_model="test-model")
        existing_msg3 = ContextMessage(role="assistant", content="Hi there!", chat_model="test-model")
        existing_msg4 = ContextMessage(role="user", content="How are you?", chat_model="test-model")
        existing_msg5 = ContextMessage(role="assistant", content="I'm doing well, thanks!", chat_model="test-model")
        mock_get_context.return_value = [existing_msg1, existing_msg2, existing_msg3, existing_msg4, existing_msg5]

        # New messages with fewer messages
        new_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        # Track conversation
        provider._track_conversation(new_messages)

        # Verify no messages were added (since there are no new messages)
        mock_add.assert_not_called()

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.add_context_messages")
    def test_conversation_with_different_system_message(self, mock_add, mock_get_context, provider):
        """Test conversation with a different system message."""
        # Mock existing context messages
        existing_msg1 = ContextMessage(role="system", content="You are a helpful assistant.", chat_model="test-model")
        existing_msg2 = ContextMessage(role="user", content="Hello", chat_model="test-model")
        existing_msg3 = ContextMessage(role="assistant", content="Hi there!", chat_model="test-model")
        mock_get_context.return_value = [existing_msg1, existing_msg2, existing_msg3]

        # New messages with a different system message
        new_messages = [
            {"role": "system", "content": "You are a friendly AI assistant."},  # Different system message
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        # Track conversation
        provider._track_conversation(new_messages)

        # Verify no messages were added (system messages are ignored in comparison)
        mock_add.assert_not_called()
