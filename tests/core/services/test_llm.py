from unittest.mock import MagicMock, patch

import pytest

from elroy.core.config import ElroyConfig
from elroy.core.services.llm import LLMService


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return ElroyConfig(
        chat_model="gpt-4",
        embedding_model="text-embedding-ada-002",
        embedding_model_size=1536,
        openai_api_key="test-api-key",
        openai_api_base="https://api.openai.com/v1",
        enable_caching=True,
        inline_tool_calls=False,
    )


@pytest.fixture
def llm_service(mock_config):
    """Create a LLMService instance with mock config."""
    return LLMService(mock_config)


def test_llm_service_init(llm_service, mock_config):
    """Test that LLMService initializes correctly."""
    assert llm_service.config == mock_config


def test_is_chat_model_inferred_false(llm_service):
    """Test is_chat_model_inferred property when chat_model is set."""
    assert not llm_service.is_chat_model_inferred


def test_is_chat_model_inferred_true():
    """Test is_chat_model_inferred property when chat_model is None."""
    config = ElroyConfig(chat_model=None)
    service = LLMService(config)
    assert service.is_chat_model_inferred


@patch("elroy.core.services.llm.infer_chat_model_name")
@patch("elroy.core.services.llm.get_chat_model")
def test_chat_model_lazy_initialization_with_model(mock_get_chat_model, mock_infer_name, llm_service):
    """Test that chat_model is lazily initialized when model name is provided."""
    mock_chat_model = MagicMock()
    mock_get_chat_model.return_value = mock_chat_model

    # Access chat_model for the first time
    result = llm_service.chat_model

    # Verify that get_chat_model was called with correct parameters
    mock_get_chat_model.assert_called_once_with(
        model_name="gpt-4",
        openai_api_key="test-api-key",
        openai_api_base="https://api.openai.com/v1",
        api_key=None,
        api_base=None,
        enable_caching=True,
        inline_tool_calls=False,
    )
    assert result == mock_chat_model

    # Verify that infer_chat_model_name was not called
    mock_infer_name.assert_not_called()


@patch("elroy.core.services.llm.infer_chat_model_name")
@patch("elroy.core.services.llm.get_chat_model")
def test_chat_model_lazy_initialization_without_model(mock_get_chat_model, mock_infer_name):
    """Test that chat_model is lazily initialized when model name is not provided."""
    config = ElroyConfig(
        chat_model=None,
        openai_api_key="test-api-key",
        openai_api_base="https://api.openai.com/v1",
        enable_caching=True,
        inline_tool_calls=False,
    )
    service = LLMService(config)

    mock_infer_name.return_value = "inferred-model"
    mock_chat_model = MagicMock()
    mock_get_chat_model.return_value = mock_chat_model

    # Access chat_model for the first time
    result = service.chat_model

    # Verify that infer_chat_model_name was called
    mock_infer_name.assert_called_once()

    # Verify that get_chat_model was called with inferred model name
    mock_get_chat_model.assert_called_once_with(
        model_name="inferred-model",
        openai_api_key="test-api-key",
        openai_api_base="https://api.openai.com/v1",
        api_key=None,
        api_base=None,
        enable_caching=True,
        inline_tool_calls=False,
    )
    assert result == mock_chat_model


@patch("elroy.core.services.llm.get_embedding_model")
def test_embedding_model_lazy_initialization(mock_get_embedding_model, llm_service):
    """Test that embedding_model is lazily initialized."""
    mock_embedding_model = MagicMock()
    mock_get_embedding_model.return_value = mock_embedding_model

    # Access embedding_model for the first time
    result = llm_service.embedding_model

    # Verify that get_embedding_model was called with correct parameters
    mock_get_embedding_model.assert_called_once_with(
        model_name="text-embedding-ada-002",
        embedding_size=1536,
        api_key=None,
        api_base=None,
        openai_embedding_api_base=None,
        openai_api_key="test-api-key",
        openai_api_base="https://api.openai.com/v1",
        enable_caching=True,
    )
    assert result == mock_embedding_model
