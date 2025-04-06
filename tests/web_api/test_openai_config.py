"""
Tests for the OpenAI-compatible server configuration.
"""

import os
from unittest import mock

from elroy.web_api.openai_compatible.config import OpenAIServerConfig, get_config


def test_default_config():
    """Test that the default configuration is loaded correctly."""
    config = OpenAIServerConfig()

    assert config.port == 8000
    assert config.host == "127.0.0.1"
    assert config.enable_auth is False
    assert config.api_keys == []
    assert config.enable_memory_creation is True
    assert config.memory_creation_interval == 10
    assert config.max_memories_per_request == 5
    assert config.relevance_threshold == 0.7


def test_config_from_env():
    """Test that configuration is loaded from environment variables."""
    with mock.patch.dict(
        os.environ,
        {
            "PORT": "9000",
            "HOST": "0.0.0.0",
            "ENABLE_AUTH": "true",
            "API_KEYS": "key1,key2,key3",
            "ENABLE_MEMORY_CREATION": "false",
            "MEMORY_CREATION_INTERVAL": "5",
            "MAX_MEMORIES_PER_REQUEST": "10",
            "RELEVANCE_THRESHOLD": "0.5",
        },
    ):
        config = OpenAIServerConfig.from_env()

        assert config.port == 9000
        assert config.host == "0.0.0.0"
        assert config.enable_auth is True
        assert config.api_keys == ["key1", "key2", "key3"]
        assert config.enable_memory_creation is False
        assert config.memory_creation_interval == 5
        assert config.max_memories_per_request == 10
        assert config.relevance_threshold == 0.5


def test_get_config():
    """Test that get_config returns a configuration object."""
    config = get_config()

    assert isinstance(config, OpenAIServerConfig)
    assert hasattr(config, "port")
    assert hasattr(config, "host")
    assert hasattr(config, "enable_auth")
    assert hasattr(config, "api_keys")
    assert hasattr(config, "enable_memory_creation")
    assert hasattr(config, "memory_creation_interval")
    assert hasattr(config, "max_memories_per_request")
    assert hasattr(config, "relevance_threshold")


def test_empty_api_keys():
    """Test that empty API keys are handled correctly."""
    with mock.patch.dict(
        os.environ,
        {
            "API_KEYS": "",
        },
    ):
        config = OpenAIServerConfig.from_env()

        assert config.api_keys == []


def test_whitespace_api_keys():
    """Test that API keys with whitespace are handled correctly."""
    with mock.patch.dict(
        os.environ,
        {
            "API_KEYS": "  key1  ,  key2  ,  key3  ",
        },
    ):
        config = OpenAIServerConfig.from_env()

        assert config.api_keys == ["key1", "key2", "key3"]
