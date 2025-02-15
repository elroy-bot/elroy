import os
from unittest.mock import patch

import pytest

from elroy.config.constants import (
    CLAUDE_3_5_SONNET,
    GEMINI_2_0_FLASH,
    GPT_4O,
    TEXT_EMBEDDING_3_SMALL,
)
from elroy.config.llm import infer_chat_model_name, infer_embedding_model_name


def test_infer_chat_model_anthropic():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        assert infer_chat_model_name() == CLAUDE_3_5_SONNET


def test_infer_chat_model_openai():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        assert infer_chat_model_name() == GPT_4O


def test_infer_chat_model_gemini():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        assert infer_chat_model_name() == GEMINI_2_0_FLASH


def test_infer_chat_model_no_keys():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Could not infer chat model"):
            infer_chat_model_name()


def test_infer_embedding_model_openai():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        assert infer_embedding_model_name() == TEXT_EMBEDDING_3_SMALL


def test_infer_embedding_model_no_keys():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="Could not infer embedding model"):
            infer_embedding_model_name()


def test_infer_embedding_model_gemini_not_supported():
    """Test that Gemini embeddings are not yet supported"""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        with pytest.raises(ValueError, match="Could not infer embedding model"):
            infer_embedding_model_name()
