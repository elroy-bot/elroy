from unittest.mock import MagicMock, patch

import pytest

from elroy.core.ctx import ElroyContext
from elroy.db.db_models import Memory
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


class TestOpenAIMemoryIntegration:
    """Tests for the memory integration in the OpenAI-compatible API."""

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_relevant_memories_and_goals")
    def test_memory_augmentation(self, mock_get_relevant, provider):
        """Test that memories are correctly augmented in the messages."""
        # Create mock memories
        memory1 = MagicMock(spec=Memory)
        memory1.to_fact.return_value = "User likes coffee"

        memory2 = MagicMock(spec=Memory)
        memory2.to_fact.return_value = "User is a software engineer"

        # Set up the mock to return our test memories
        mock_get_relevant.return_value = [memory1, memory2]

        # Test messages
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "Hello, how are you?"}]

        # Get augmented messages
        augmented_messages = provider._get_augmented_messages(messages)

        # Verify the augmentation
        assert len(augmented_messages) == 4
        assert augmented_messages[0] == {"role": "system", "content": "You are a helpful assistant."}
        assert augmented_messages[1] == {"role": "system", "content": "Relevant memory: User likes coffee"}
        assert augmented_messages[2] == {"role": "system", "content": "Relevant memory: User is a software engineer"}
        assert augmented_messages[3] == {"role": "user", "content": "Hello, how are you?"}

        # Verify the memory retrieval was called with the correct query
        mock_get_relevant.assert_called_once_with(provider.ctx, "Hello, how are you?")

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.formulate_memory")
    @patch("elroy.web_api.openai_compatible.litellm_provider.do_create_memory_from_ctx_msgs")
    def test_memory_creation(self, mock_create, mock_formulate, mock_get_context, provider):
        """Test that memories are created from conversations."""
        # Mock context messages
        context_messages = []
        for i in range(12):  # More than the threshold of 10
            if i % 2 == 0:
                context_messages.append(ContextMessage(role="user", content=f"User message {i}", chat_model="test-model"))
            else:
                context_messages.append(ContextMessage(role="assistant", content=f"Assistant message {i}", chat_model="test-model"))

        mock_get_context.return_value = context_messages
        mock_formulate.return_value = ("Test Memory", "This is a test memory")

        # Test memory creation
        provider._create_memory_if_needed({})

        # Verify memory creation
        mock_formulate.assert_called_once_with(provider.ctx, context_messages)
        mock_create.assert_called_once_with(provider.ctx, "Test Memory", "This is a test memory")

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.add_context_messages")
    def test_conversation_tracking(self, mock_add, mock_get_context, provider):
        """Test that conversations are tracked correctly."""
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

        # Verify conversation tracking
        mock_add.assert_called_once()
        added_messages = mock_add.call_args[0][1]
        assert len(added_messages) == 1
        assert added_messages[0].role == "user"
        assert added_messages[0].content == "What's the weather like?"

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.add_context_messages")
    def test_conversation_divergence(self, mock_add, mock_get_context, provider):
        """Test that conversation divergence is handled correctly."""
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

        # Track conversation
        provider._track_conversation(new_messages)

        # Verify divergence handling
        mock_add.assert_called_once()
        added_messages = mock_add.call_args[0][1]
        assert len(added_messages) == 1
        assert added_messages[0].role == "user"
        assert added_messages[0].content == "What's the weather like?"

    @patch("litellm.completion")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._track_conversation")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._get_augmented_messages")
    def test_end_to_end_completion(self, mock_augment, mock_track, mock_completion, provider):
        """Test the end-to-end completion flow with memory integration."""
        # Mock messages
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "Hello, how are you?"}]

        # Mock augmented messages
        augmented_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "system", "content": "Relevant memory: User likes coffee"},
            {"role": "user", "content": "Hello, how are you?"},
        ]
        mock_augment.return_value = augmented_messages

        # Create a response object with the necessary structure
        # Create a response object with the necessary structure
        class Choice:
            def __init__(self):
                self.index = 0
                self.message = self.Message()
                self.finish_reason = "stop"

            class Message:
                def __init__(self):
                    self.role = "assistant"
                    self.content = "I'm doing well! Would you like some coffee?"

        class MockResponse:
            def __init__(self):
                self.id = "test-id"
                self.object = "chat.completion"
                self.created = 1234567890
                self.model = "test-model"
                self.choices = [Choice()]
                self.usage = {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}

            def __getitem__(self, key):
                return getattr(self, key)

            def get(self, key, default=None):
                return getattr(self, key, default)

            def to_dict(self):
                return {
                    "id": self.id,
                    "object": self.object,
                    "created": self.created,
                    "model": self.model,
                    "choices": [
                        {
                            "index": self.choices[0].index,
                            "message": {"role": self.choices[0].message.role, "content": self.choices[0].message.content},
                            "finish_reason": self.choices[0].finish_reason,
                        }
                    ],
                    "usage": self.usage,
                }

        mock_response = MockResponse()
        mock_completion.return_value = mock_response

        # Patch the _create_memory_if_needed method directly
        with patch.object(provider, "_create_memory_if_needed") as mock_create_memory:
            # Call completion
            result = provider.completion("test-model", messages)

            # Verify the flow
            mock_track.assert_called_once_with(messages)
            mock_augment.assert_called_once_with(messages)

            # Verify litellm.completion was called with augmented messages
            mock_completion.assert_called_once()
            args, kwargs = mock_completion.call_args
            assert kwargs["messages"] == augmented_messages

            # Verify memory creation was attempted
            mock_create_memory.assert_called_once()

        # Verify the response
        assert result == mock_response
