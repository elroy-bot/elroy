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
    ctx.l2_memory_relevance_distance_threshold = 0.7
    ctx.messages_between_memory = 10
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


class TestElroyLiteLLMProvider:
    """Tests for the ElroyLiteLLMProvider class."""

    def test_init(self, provider, mock_ctx):
        """Test initialization of the provider."""
        assert provider.ctx == mock_ctx
        assert provider.enable_memory_creation is True
        assert provider.memory_creation_interval == 10
        assert provider.max_memories_per_request == 5

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_relevant_memories_and_goals")
    def test_get_augmented_messages_no_user_messages(self, mock_get_relevant, provider):
        """Test augmentation when there are no user messages."""
        messages = [{"role": "system", "content": "You are a helpful assistant."}]

        result = provider._get_augmented_messages(messages)

        # Should return original messages without augmentation
        assert result == messages
        mock_get_relevant.assert_not_called()

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_relevant_memories_and_goals")
    def test_get_augmented_messages_no_relevant_memories(self, mock_get_relevant, provider):
        """Test augmentation when there are no relevant memories."""
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "Hello, how are you?"}]

        # Mock no relevant memories found
        mock_get_relevant.return_value = []

        result = provider._get_augmented_messages(messages)

        # Should return original messages without augmentation
        assert result == messages
        mock_get_relevant.assert_called_once()

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_relevant_memories_and_goals")
    def test_get_augmented_messages_with_relevant_memories(self, mock_get_relevant, provider):
        """Test augmentation with relevant memories."""
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "Hello, how are you?"}]

        # Mock relevant memories
        memory1 = MagicMock()
        memory1.to_fact.return_value = "User likes coffee"

        memory2 = MagicMock()
        memory2.to_fact.return_value = "User is a software engineer"

        mock_get_relevant.return_value = [memory1, memory2]

        result = provider._get_augmented_messages(messages)

        # Should include original system message, memory context, and user message
        assert len(result) == 4
        assert result[0] == {"role": "system", "content": "You are a helpful assistant."}
        assert result[1] == {"role": "system", "content": "Relevant memory: User likes coffee"}
        assert result[2] == {"role": "system", "content": "Relevant memory: User is a software engineer"}
        assert result[3] == {"role": "user", "content": "Hello, how are you?"}

        mock_get_relevant.assert_called_once()

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.add_context_messages")
    def test_track_conversation_no_divergence(self, mock_add, mock_get_context, provider):
        """Test conversation tracking with no divergence."""
        # Mock existing context messages
        existing_msg1 = ContextMessage(role="system", content="You are a helpful assistant.", chat_model="test-model")
        existing_msg2 = ContextMessage(role="user", content="Hello", chat_model="test-model")
        mock_get_context.return_value = [existing_msg1, existing_msg2]

        # New messages with one additional message
        new_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        provider._track_conversation(new_messages)

        # Should add only the new assistant message
        mock_add.assert_called_once()
        added_messages = mock_add.call_args[0][1]
        assert len(added_messages) == 1
        assert added_messages[0].role == "assistant"
        assert added_messages[0].content == "Hi there!"

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.add_context_messages")
    def test_track_conversation_with_divergence(self, mock_add, mock_get_context, provider):
        """Test conversation tracking with divergence."""
        # Mock existing context messages
        existing_msg1 = ContextMessage(role="system", content="You are a helpful assistant.", chat_model="test-model")
        existing_msg2 = ContextMessage(role="user", content="Hello", chat_model="test-model")
        existing_msg3 = ContextMessage(role="assistant", content="Hi there!", chat_model="test-model")
        existing_msg4 = ContextMessage(role="user", content="How are you?", chat_model="test-model")
        mock_get_context.return_value = [existing_msg1, existing_msg2, existing_msg3, existing_msg4]

        # New messages with divergence at the second user message
        new_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "What's the weather like?"},  # Different from "How are you?"
        ]

        provider._track_conversation(new_messages)

        # Should add the divergent message
        mock_add.assert_called_once()
        added_messages = mock_add.call_args[0][1]
        assert len(added_messages) == 1
        assert added_messages[0].role == "user"
        assert added_messages[0].content == "What's the weather like?"

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.formulate_memory")
    @patch("elroy.web_api.openai_compatible.litellm_provider.do_create_memory_from_ctx_msgs")
    def test_create_memory_if_needed_threshold_met(self, mock_create, mock_formulate, mock_get_context, provider):
        """Test memory creation when threshold is met."""
        # Mock context messages with enough user/assistant messages
        context_messages = []
        for i in range(12):  # More than the threshold of 10
            if i % 2 == 0:
                context_messages.append(ContextMessage(role="user", content=f"User message {i}", chat_model="test-model"))
            else:
                context_messages.append(ContextMessage(role="assistant", content=f"Assistant message {i}", chat_model="test-model"))

        mock_get_context.return_value = context_messages
        mock_formulate.return_value = ("Test Memory", "This is a test memory")

        provider._create_memory_if_needed({})

        # Should create a memory
        mock_formulate.assert_called_once_with(provider.ctx, context_messages)
        mock_create.assert_called_once_with(provider.ctx, "Test Memory", "This is a test memory")

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.formulate_memory")
    @patch("elroy.web_api.openai_compatible.litellm_provider.do_create_memory_from_ctx_msgs")
    def test_create_memory_if_needed_threshold_not_met(self, mock_create, mock_formulate, mock_get_context, provider):
        """Test memory creation when threshold is not met."""
        # Mock context messages with not enough user/assistant messages
        context_messages = []
        for i in range(4):  # Less than the threshold of 10
            if i % 2 == 0:
                context_messages.append(ContextMessage(role="user", content=f"User message {i}", chat_model="test-model"))
            else:
                context_messages.append(ContextMessage(role="assistant", content=f"Assistant message {i}", chat_model="test-model"))

        mock_get_context.return_value = context_messages

        provider._create_memory_if_needed({})

        # Should not create a memory
        mock_formulate.assert_not_called()
        mock_create.assert_not_called()

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.formulate_memory")
    @patch("elroy.web_api.openai_compatible.litellm_provider.do_create_memory_from_ctx_msgs")
    def test_create_memory_if_needed_disabled(self, mock_create, mock_formulate, mock_get_context, provider):
        """Test memory creation when disabled."""
        # Disable memory creation
        provider.enable_memory_creation = False

        provider._create_memory_if_needed({})

        # Should not create a memory
        mock_get_context.assert_not_called()
        mock_formulate.assert_not_called()
        mock_create.assert_not_called()

    @patch("litellm.completion")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._track_conversation")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._get_augmented_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._prepare_response")
    def test_completion(self, mock_prepare, mock_augment, mock_track, mock_completion, provider):
        """Test the completion method."""
        messages = [{"role": "user", "content": "Hello"}]
        augmented_messages = [{"role": "system", "content": "Relevant memory: User likes coffee"}, {"role": "user", "content": "Hello"}]
        mock_augment.return_value = augmented_messages

        mock_response = MagicMock()
        mock_completion.return_value = mock_response
        mock_prepare.return_value = mock_response

        result = provider.completion("test-model", messages, temperature=0.7)

        # Should track conversation, augment messages, and call litellm.completion
        mock_track.assert_called_once_with(messages)
        mock_augment.assert_called_once_with(messages)
        mock_completion.assert_called_once()
        mock_prepare.assert_called_once_with(mock_response, "test-model")
        assert result == mock_response

    @patch("litellm.completion")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._track_conversation")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._get_augmented_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._create_memory_if_needed")
    def test_streaming(self, mock_create_memory, mock_augment, mock_track, mock_completion, provider):
        """Test the streaming method."""
        messages = [{"role": "user", "content": "Hello"}]
        augmented_messages = [{"role": "system", "content": "Relevant memory: User likes coffee"}, {"role": "user", "content": "Hello"}]
        mock_augment.return_value = augmented_messages

        # Mock streaming response
        chunk1 = MagicMock()
        chunk2 = MagicMock()
        mock_completion.return_value = [chunk1, chunk2]

        result = list(provider.streaming("test-model", messages, temperature=0.7))

        # Should track conversation, augment messages, and call litellm.completion
        mock_track.assert_called_once_with(messages)
        mock_augment.assert_called_once_with(messages)
        mock_completion.assert_called_once()
        mock_create_memory.assert_called_once_with(messages)
        assert result == [chunk1, chunk2]
