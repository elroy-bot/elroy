"""
Tests for authentication in the OpenAI-compatible server.
"""

from unittest import mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from elroy.web_api.openai_compatible.config import OpenAIServerConfig
from elroy.web_api.openai_compatible.server import app, verify_api_key


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_config():
    """Mock the get_config function."""
    with mock.patch("elroy.web_api.openai_compatible.server.get_config") as mock_get_config:
        # Create a mock config
        mock_config = OpenAIServerConfig()

        # Set up the mock to return our mock config
        mock_get_config.return_value = mock_config

        yield mock_config


def test_verify_api_key_auth_disabled(mock_config):
    """Test that API key verification passes when auth is disabled."""
    # Disable authentication
    mock_config.enable_auth = False

    # Verify the API key
    result = verify_api_key(None)

    # Check the result
    assert result is True


def test_verify_api_key_auth_enabled_missing_key(mock_config):
    """Test that API key verification fails when auth is enabled but key is missing."""
    # Enable authentication
    mock_config.enable_auth = True
    mock_config.api_keys = ["test-key"]

    # Verify the API key
    with pytest.raises(HTTPException) as excinfo:
        verify_api_key(None)

    # Check the exception
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Missing API key"


def test_verify_api_key_auth_enabled_invalid_key(mock_config):
    """Test that API key verification fails when auth is enabled but key is invalid."""
    # Enable authentication
    mock_config.enable_auth = True
    mock_config.api_keys = ["test-key"]

    # Verify the API key
    with pytest.raises(HTTPException) as excinfo:
        verify_api_key("invalid-key")

    # Check the exception
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Invalid API key"


def test_verify_api_key_auth_enabled_valid_key(mock_config):
    """Test that API key verification passes when auth is enabled and key is valid."""
    # Enable authentication
    mock_config.enable_auth = True
    mock_config.api_keys = ["test-key"]

    # Verify the API key
    result = verify_api_key("test-key")

    # Check the result
    assert result is True


def test_verify_api_key_auth_enabled_valid_key_with_bearer(mock_config):
    """Test that API key verification passes when auth is enabled and key is valid with Bearer prefix."""
    # Enable authentication
    mock_config.enable_auth = True
    mock_config.api_keys = ["test-key"]

    # Verify the API key
    result = verify_api_key("Bearer test-key")

    # Check the result
    assert result is True


def test_chat_completions_endpoint_auth_disabled(client, mock_config):
    """Test that the chat completions endpoint works when auth is disabled."""
    # Disable authentication
    mock_config.enable_auth = False

    # Mock the get_context function
    with mock.patch("elroy.web_api.openai_compatible.server.get_context") as mock_get_context:
        # Create a mock context
        mock_ctx = mock.MagicMock()

        # Set up the mock to return our mock context
        mock_get_context.return_value = mock_ctx

        # Mock the conversation tracker
        with mock.patch("elroy.web_api.openai_compatible.server.ConversationTracker") as mock_tracker_cls:
            # Create a mock tracker instance
            mock_tracker = mock.MagicMock()
            mock_tracker.compare_and_update_conversation.return_value = ([], False)

            # Set up the mock class to return our mock tracker
            mock_tracker_cls.return_value = mock_tracker

            # Mock the get_relevant_memories_for_conversation function
            with mock.patch("elroy.web_api.openai_compatible.server.get_relevant_memories_for_conversation") as mock_get_memories:
                # Set up the mock to return an empty list
                mock_get_memories.return_value = []

                # Mock the generate_chat_completion function
                with mock.patch("elroy.web_api.openai_compatible.server.generate_chat_completion") as mock_generate:
                    # Create a mock response
                    mock_response = mock.MagicMock()

                    # Set up the mock to return our mock response
                    mock_generate.return_value = mock_response

                    # Create a test request
                    request_data = {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": "Hello, how are you?"},
                        ],
                    }

                    # Send the request without an API key
                    response = client.post(
                        "/v1/chat/completions",
                        json=request_data,
                    )

                    # Check the response
                    assert response.status_code == 200


def test_chat_completions_endpoint_auth_enabled_missing_key(client, mock_config):
    """Test that the chat completions endpoint fails when auth is enabled but key is missing."""
    # Enable authentication
    mock_config.enable_auth = True
    mock_config.api_keys = ["test-key"]

    # Create a test request
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ],
    }

    # Send the request without an API key
    response = client.post(
        "/v1/chat/completions",
        json=request_data,
    )

    # Check the response
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_chat_completions_endpoint_auth_enabled_invalid_key(client, mock_config):
    """Test that the chat completions endpoint fails when auth is enabled but key is invalid."""
    # Enable authentication
    mock_config.enable_auth = True
    mock_config.api_keys = ["test-key"]

    # Create a test request
    request_data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ],
    }

    # Send the request with an invalid API key
    response = client.post(
        "/v1/chat/completions",
        json=request_data,
        headers={"Authorization": "invalid-key"},
    )

    # Check the response
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_chat_completions_endpoint_auth_enabled_valid_key(client, mock_config):
    """Test that the chat completions endpoint works when auth is enabled and key is valid."""
    # Enable authentication
    mock_config.enable_auth = True
    mock_config.api_keys = ["test-key"]

    # Mock the get_context function
    with mock.patch("elroy.web_api.openai_compatible.server.get_context") as mock_get_context:
        # Create a mock context
        mock_ctx = mock.MagicMock()

        # Set up the mock to return our mock context
        mock_get_context.return_value = mock_ctx

        # Mock the conversation tracker
        with mock.patch("elroy.web_api.openai_compatible.server.ConversationTracker") as mock_tracker_cls:
            # Create a mock tracker instance
            mock_tracker = mock.MagicMock()
            mock_tracker.compare_and_update_conversation.return_value = ([], False)

            # Set up the mock class to return our mock tracker
            mock_tracker_cls.return_value = mock_tracker

            # Mock the get_relevant_memories_for_conversation function
            with mock.patch("elroy.web_api.openai_compatible.server.get_relevant_memories_for_conversation") as mock_get_memories:
                # Set up the mock to return an empty list
                mock_get_memories.return_value = []

                # Mock the generate_chat_completion function
                with mock.patch("elroy.web_api.openai_compatible.server.generate_chat_completion") as mock_generate:
                    # Create a mock response
                    mock_response = mock.MagicMock()

                    # Set up the mock to return our mock response
                    mock_generate.return_value = mock_response

                    # Create a test request
                    request_data = {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": "Hello, how are you?"},
                        ],
                    }

                    # Send the request with a valid API key
                    response = client.post(
                        "/v1/chat/completions",
                        json=request_data,
                        headers={"Authorization": "Bearer test-key"},
                    )

                    # Check the response
                    assert response.status_code == 200


def test_models_endpoint_auth_enabled_valid_key(client, mock_config):
    """Test that the models endpoint works when auth is enabled and key is valid."""
    # Enable authentication
    mock_config.enable_auth = True
    mock_config.api_keys = ["test-key"]

    # Send the request with a valid API key
    response = client.get(
        "/v1/models",
        headers={"Authorization": "Bearer test-key"},
    )

    # Check the response
    assert response.status_code == 200
    assert "data" in response.json()
    assert len(response.json()["data"]) > 0


def test_models_endpoint_auth_enabled_invalid_key(client, mock_config):
    """Test that the models endpoint fails when auth is enabled but key is invalid."""
    # Enable authentication
    mock_config.enable_auth = True
    mock_config.api_keys = ["test-key"]

    # Send the request with an invalid API key
    response = client.get(
        "/v1/models",
        headers={"Authorization": "invalid-key"},
    )

    # Check the response
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_root_endpoint_no_auth_required(client, mock_config):
    """Test that the root endpoint works without authentication."""
    # Enable authentication
    mock_config.enable_auth = True
    mock_config.api_keys = ["test-key"]

    # Send the request without an API key
    response = client.get("/")

    # Check the response
    assert response.status_code == 200
    assert "message" in response.json()
    assert "version" in response.json()
    assert "documentation" in response.json()
