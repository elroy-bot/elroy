from datetime import timedelta

import pytest

from elroy.core.config import ElroyConfig
from elroy.core.services.memory import MemoryService


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return ElroyConfig(max_context_age_minutes=60, min_convo_age_for_greeting_minutes=30)


@pytest.fixture
def memory_service(mock_config):
    """Create a MemoryService instance with mock config."""
    return MemoryService(mock_config)


def test_memory_service_init(memory_service, mock_config):
    """Test that MemoryService initializes correctly."""
    assert memory_service.config == mock_config


def test_max_in_context_message_age(memory_service):
    """Test max_in_context_message_age property."""
    expected_timedelta = timedelta(minutes=60)
    assert memory_service.max_in_context_message_age == expected_timedelta


def test_min_convo_age_for_greeting(memory_service):
    """Test min_convo_age_for_greeting property."""
    expected_timedelta = timedelta(minutes=30)
    assert memory_service.min_convo_age_for_greeting == expected_timedelta


def test_max_in_context_message_age_default():
    """Test max_in_context_message_age property with default value."""
    config = ElroyConfig()  # No max_context_age_minutes provided
    service = MemoryService(config)

    # Default value should be 0 minutes
    expected_timedelta = timedelta(minutes=0)
    assert service.max_in_context_message_age == expected_timedelta


def test_min_convo_age_for_greeting_default():
    """Test min_convo_age_for_greeting property with default value."""
    config = ElroyConfig()  # No min_convo_age_for_greeting_minutes provided
    service = MemoryService(config)

    # Default value should be 0 minutes
    expected_timedelta = timedelta(minutes=0)
    assert service.min_convo_age_for_greeting == expected_timedelta
