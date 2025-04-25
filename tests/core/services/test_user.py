from unittest.mock import MagicMock, patch

import pytest

from elroy.core.config import ElroyConfig
from elroy.core.services.database import DatabaseService
from elroy.core.services.user import UserService


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return ElroyConfig(user_token="test-user-token")


@pytest.fixture
def mock_db_service():
    """Create a mock database service."""
    db_service = MagicMock(spec=DatabaseService)
    mock_db = MagicMock()
    db_service.db = mock_db
    return db_service


@pytest.fixture
def user_service(mock_config, mock_db_service):
    """Create a UserService instance with mock config and db service."""
    return UserService(mock_config, mock_db_service)


def test_user_service_init(user_service, mock_config, mock_db_service):
    """Test that UserService initializes correctly."""
    assert user_service.config == mock_config
    assert user_service.db_service == mock_db_service


@patch("elroy.repository.user.queries.get_user_id_if_exists")
@patch("elroy.repository.user.operations.create_user_id")
def test_user_id_existing_user(mock_create_user_id, mock_get_user_id, user_service, mock_db_service):
    """Test user_id property when user exists."""
    mock_get_user_id.return_value = 123

    # Access user_id for the first time
    result = user_service.user_id

    # Verify that get_user_id_if_exists was called with correct parameters
    mock_get_user_id.assert_called_once_with(mock_db_service.db, "test-user-token")

    # Verify that create_user_id was not called
    mock_create_user_id.assert_not_called()

    assert result == 123


@patch("elroy.repository.user.queries.get_user_id_if_exists")
@patch("elroy.repository.user.operations.create_user_id")
def test_user_id_new_user(mock_create_user_id, mock_get_user_id, user_service, mock_db_service):
    """Test user_id property when user does not exist."""
    mock_get_user_id.return_value = None
    mock_create_user_id.return_value = 456

    # Access user_id for the first time
    result = user_service.user_id

    # Verify that get_user_id_if_exists was called with correct parameters
    mock_get_user_id.assert_called_once_with(mock_db_service.db, "test-user-token")

    # Verify that create_user_id was called with correct parameters
    mock_create_user_id.assert_called_once_with(mock_db_service.db, "test-user-token")

    assert result == 456


@patch("elroy.repository.user.queries.get_user_id_if_exists")
def test_user_id_cached(mock_get_user_id, user_service):
    """Test that user_id is cached after first access."""
    # We need to patch create_user_id too to avoid actual calls
    with patch("elroy.repository.user.operations.create_user_id"):
        mock_get_user_id.return_value = 789

        # Access user_id for the first time
        result1 = user_service.user_id
        assert result1 == 789

        # Access user_id again
        result2 = user_service.user_id

        # Verify that get_user_id_if_exists was called only once (cached_property)
        assert mock_get_user_id.call_count == 1
        assert result2 == 789
