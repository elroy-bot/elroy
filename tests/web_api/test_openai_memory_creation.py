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


class TestOpenAIMemoryCreation:
    """Tests for the memory creation functionality in the OpenAI-compatible API."""

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.formulate_memory")
    @patch("elroy.web_api.openai_compatible.litellm_provider.do_create_memory_from_ctx_msgs")
    def test_memory_creation_when_threshold_met(self, mock_create, mock_formulate, mock_get_context, provider):
        """Test memory creation when the threshold is met."""
        # Mock context messages with enough user/assistant messages
        context_messages = []
        for i in range(12):  # More than the threshold of 10
            if i % 2 == 0:
                context_messages.append(ContextMessage(role="user", content=f"User message {i}", chat_model="test-model"))
            else:
                context_messages.append(ContextMessage(role="assistant", content=f"Assistant message {i}", chat_model="test-model"))

        mock_get_context.return_value = context_messages
        mock_formulate.return_value = ("Test Memory", "This is a test memory")

        # Call the memory creation function
        provider._create_memory_if_needed({})

        # Verify memory creation
        mock_formulate.assert_called_once_with(provider.ctx, context_messages)
        mock_create.assert_called_once_with(provider.ctx, "Test Memory", "This is a test memory")

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.formulate_memory")
    @patch("elroy.web_api.openai_compatible.litellm_provider.do_create_memory_from_ctx_msgs")
    def test_memory_creation_when_threshold_not_met(self, mock_create, mock_formulate, mock_get_context, provider):
        """Test memory creation when the threshold is not met."""
        # Mock context messages with not enough user/assistant messages
        context_messages = []
        for i in range(4):  # Less than the threshold of 10
            if i % 2 == 0:
                context_messages.append(ContextMessage(role="user", content=f"User message {i}", chat_model="test-model"))
            else:
                context_messages.append(ContextMessage(role="assistant", content=f"Assistant message {i}", chat_model="test-model"))

        mock_get_context.return_value = context_messages

        # Call the memory creation function
        provider._create_memory_if_needed({})

        # Verify no memory creation
        mock_formulate.assert_not_called()
        mock_create.assert_not_called()

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.formulate_memory")
    @patch("elroy.web_api.openai_compatible.litellm_provider.do_create_memory_from_ctx_msgs")
    def test_memory_creation_when_disabled(self, mock_create, mock_formulate, mock_get_context, provider):
        """Test memory creation when it's disabled."""
        # Disable memory creation
        provider.enable_memory_creation = False

        # Call the memory creation function
        provider._create_memory_if_needed({})

        # Verify no memory creation
        mock_get_context.assert_not_called()
        mock_formulate.assert_not_called()
        mock_create.assert_not_called()

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.formulate_memory")
    @patch("elroy.web_api.openai_compatible.litellm_provider.do_create_memory_from_ctx_msgs")
    def test_memory_creation_with_custom_interval(self, mock_create, mock_formulate, mock_get_context, provider):
        """Test memory creation with a custom interval."""
        # Set a custom memory creation interval
        provider.memory_creation_interval = 5

        # Mock context messages with enough user/assistant messages for the custom threshold
        context_messages = []
        for i in range(6):  # More than the threshold of 5
            if i % 2 == 0:
                context_messages.append(ContextMessage(role="user", content=f"User message {i}", chat_model="test-model"))
            else:
                context_messages.append(ContextMessage(role="assistant", content=f"Assistant message {i}", chat_model="test-model"))

        mock_get_context.return_value = context_messages
        mock_formulate.return_value = ("Test Memory", "This is a test memory")

        # Call the memory creation function
        provider._create_memory_if_needed({})

        # Verify memory creation
        mock_formulate.assert_called_once_with(provider.ctx, context_messages)
        mock_create.assert_called_once_with(provider.ctx, "Test Memory", "This is a test memory")

    @patch("elroy.web_api.openai_compatible.litellm_provider.get_context_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.formulate_memory")
    @patch("elroy.web_api.openai_compatible.litellm_provider.do_create_memory_from_ctx_msgs")
    def test_memory_creation_error_handling(self, mock_create, mock_formulate, mock_get_context, provider):
        """Test error handling during memory creation."""
        # Mock context messages with enough user/assistant messages
        context_messages = []
        for i in range(12):  # More than the threshold of 10
            if i % 2 == 0:
                context_messages.append(ContextMessage(role="user", content=f"User message {i}", chat_model="test-model"))
            else:
                context_messages.append(ContextMessage(role="assistant", content=f"Assistant message {i}", chat_model="test-model"))

        mock_get_context.return_value = context_messages
        mock_formulate.side_effect = Exception("Test memory creation error")

        # Call the memory creation function
        provider._create_memory_if_needed({})

        # Verify error handling
        mock_formulate.assert_called_once_with(provider.ctx, context_messages)
        mock_create.assert_not_called()

    @patch("litellm.completion")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._track_conversation")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._get_augmented_messages")
    def test_memory_creation_after_completion(self, mock_augment, mock_track, mock_completion, provider):
        """Test memory creation after completion."""

        # Create a response object with the necessary structure
        class Choice:
            def __init__(self):
                self.index = 0
                self.message = self.Message()
                self.finish_reason = "stop"

            class Message:
                def __init__(self):
                    self.role = "assistant"
                    self.content = "Hello, how can I help you?"

        class MockResponse:
            def __init__(self):
                self.id = "test-id"
                self.object = "chat.completion"
                self.created = 1234567890
                self.model = "test-model"
                self.choices = [Choice()]
                self.usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}

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

        # Test messages
        messages = [{"role": "user", "content": "Hello"}]

        # Patch the _create_memory_if_needed method directly
        with patch.object(provider, "_create_memory_if_needed") as mock_create_memory:
            # Call completion
            provider.completion("test-model", messages)

            # Verify memory creation was attempted
            mock_create_memory.assert_called_once()

    @patch("litellm.completion")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._track_conversation")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._get_augmented_messages")
    @patch("elroy.web_api.openai_compatible.litellm_provider.ElroyLiteLLMProvider._create_memory_if_needed")
    def test_memory_creation_after_streaming(self, mock_create_memory, mock_augment, mock_track, mock_completion, provider):
        """Test memory creation after streaming."""
        # Mock streaming response chunks
        chunk1 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}'
        chunk2 = '{"id":"test-id","object":"chat.completion.chunk","created":1234567890,"model":"test-model","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}'

        # Set up the mock
        mock_completion.return_value = [chunk1, chunk2]

        # Test messages
        messages = [{"role": "user", "content": "Hello"}]

        # Call streaming
        list(provider.streaming("test-model", messages))

        # Verify memory creation was attempted
        mock_create_memory.assert_called_once_with(messages)
