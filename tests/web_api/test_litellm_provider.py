"""
Tests for the LiteLLM provider integration with Elroy.
"""

from unittest.mock import MagicMock, patch

import pytest

from elroy.core.ctx import ElroyContext
from elroy.web_api.openai_compatible.litellm_provider import ElroyLLM


@pytest.fixture
def mock_elroy_context():
    """Create a mock ElroyContext."""
    ctx = MagicMock(spec=ElroyContext)
    ctx.user_id = 1
    ctx.db = MagicMock()
    return ctx


@pytest.fixture
def mock_model_response():
    """Create a mock ModelResponse."""
    return MagicMock()


@pytest.fixture
def elroy_llm():
    """Create an ElroyLLM instance."""
    return ElroyLLM()


@patch("elroy.web_api.openai_compatible.litellm_provider.get_resolved_params")
@patch("elroy.web_api.openai_compatible.litellm_provider.ElroyContext")
@patch("elroy.web_api.openai_compatible.litellm_provider.get_config")
@patch("elroy.web_api.openai_compatible.litellm_provider.generate_chat_completion_message")
@patch("elroy.web_api.openai_compatible.litellm_provider.get_relevant_memories_for_conversation")
def test_completion_basic(
    mock_get_memories,
    mock_generate,
    mock_get_config,
    mock_elroy_context_class,
    mock_get_resolved_params,
    elroy_llm,
    mock_elroy_context,
    mock_model_response,
):
    """Test basic completion functionality."""
    # Setup mocks
    mock_get_resolved_params.return_value = {"use_background_threads": True}
    mock_elroy_context_class.return_value = mock_elroy_context
    mock_get_config.return_value = MagicMock(
        max_memories_per_request=5,
        relevance_threshold=0.7,
        enable_memory_creation=False,
    )
    mock_get_memories.return_value = []

    # Mock stream parser
    mock_stream_parser = MagicMock()
    mock_chunk = MagicMock()
    mock_chunk.content = "Hello, world!"
    mock_stream_parser.process_stream.return_value = [mock_chunk]
    mock_generate.return_value = mock_stream_parser

    # Call the method
    result = elroy_llm.completion(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello"}],
        api_base="https://api.example.com",
        custom_prompt_dict={},
        model_response=mock_model_response,
        print_verbose=lambda x: None,
        encoding=None,
        api_key="test-key",
        logging_obj=None,
        optional_params={},
    )

    # Assertions
    assert result is mock_model_response
    assert mock_generate.called
    assert mock_get_memories.called


@patch("elroy.web_api.openai_compatible.litellm_provider.get_resolved_params")
@patch("elroy.web_api.openai_compatible.litellm_provider.ElroyContext")
@patch("elroy.web_api.openai_compatible.litellm_provider.get_config")
@patch("elroy.web_api.openai_compatible.litellm_provider.generate_chat_completion_message")
@patch("elroy.web_api.openai_compatible.litellm_provider.get_relevant_memories_for_conversation")
def test_streaming_basic(
    mock_get_memories,
    mock_generate,
    mock_get_config,
    mock_elroy_context_class,
    mock_get_resolved_params,
    elroy_llm,
    mock_elroy_context,
):
    """Test basic streaming functionality."""
    # Setup mocks
    mock_get_resolved_params.return_value = {"use_background_threads": True}
    mock_elroy_context_class.return_value = mock_elroy_context
    mock_get_config.return_value = MagicMock(
        max_memories_per_request=5,
        relevance_threshold=0.7,
        enable_memory_creation=False,
    )
    mock_get_memories.return_value = []

    # Mock stream parser
    mock_stream_parser = MagicMock()
    mock_chunk = MagicMock()
    mock_chunk.content = "Hello, world!"
    mock_stream_parser.process_stream.return_value = [mock_chunk]
    mock_generate.return_value = mock_stream_parser

    # Call the method
    chunks = list(
        elroy_llm.streaming(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            api_base="https://api.example.com",
            custom_prompt_dict={},
            model_response=MagicMock(),
            print_verbose=lambda x: None,
            encoding=None,
            api_key="test-key",
            logging_obj=None,
            optional_params={},
        )
    )

    # Assertions
    assert len(chunks) > 0
    assert mock_generate.called
    assert mock_get_memories.called


@patch("elroy.web_api.openai_compatible.litellm_provider.get_resolved_params")
@patch("elroy.web_api.openai_compatible.litellm_provider.ElroyContext")
@patch("elroy.web_api.openai_compatible.litellm_provider.get_config")
@patch("elroy.web_api.openai_compatible.litellm_provider.generate_chat_completion_message")
@patch("elroy.web_api.openai_compatible.litellm_provider.get_relevant_memories_for_conversation")
def test_memory_augmentation(
    mock_get_memories,
    mock_generate,
    mock_get_config,
    mock_elroy_context_class,
    mock_get_resolved_params,
    elroy_llm,
    mock_elroy_context,
    mock_model_response,
):
    """Test that memories are correctly added to the context."""
    # Setup mocks
    mock_get_resolved_params.return_value = {"use_background_threads": True}
    mock_elroy_context_class.return_value = mock_elroy_context
    mock_get_config.return_value = MagicMock(
        max_memories_per_request=5,
        relevance_threshold=0.7,
        enable_memory_creation=False,
    )

    # Create mock memories
    mock_memory1 = MagicMock()
    mock_memory1.name = "Memory 1"
    mock_memory1.to_fact.return_value = "This is memory 1"

    mock_memory2 = MagicMock()
    mock_memory2.name = "Memory 2"
    mock_memory2.to_fact.return_value = "This is memory 2"

    mock_get_memories.return_value = [mock_memory1, mock_memory2]

    # Mock stream parser
    mock_stream_parser = MagicMock()
    mock_chunk = MagicMock()
    mock_chunk.content = "Hello, world!"
    mock_stream_parser.process_stream.return_value = [mock_chunk]
    mock_generate.return_value = mock_stream_parser

    # Call the method
    elroy_llm.completion(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello"}],
        api_base="https://api.example.com",
        custom_prompt_dict={},
        model_response=mock_model_response,
        print_verbose=lambda x: None,
        encoding=None,
        api_key="test-key",
        logging_obj=None,
        optional_params={},
    )

    # Get the augmented context messages passed to generate_chat_completion_message
    args, _ = mock_generate.call_args
    augmented_context_messages = args[1]

    # Check that memory messages are included
    memory_messages = [msg for msg in augmented_context_messages if "Memory:" in msg.content]
    assert len(memory_messages) == 2
    assert "Memory: Memory 1" in memory_messages[0].content
    assert "Memory: Memory 2" in memory_messages[1].content
