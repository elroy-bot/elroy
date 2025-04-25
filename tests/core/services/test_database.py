from unittest.mock import MagicMock, patch

import pytest

from elroy.core.config import ElroyConfig
from elroy.core.services.database import DatabaseService
from elroy.db.db_session import DbSession


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return ElroyConfig(database_url="sqlite:///test.db")


@pytest.fixture
def database_service(mock_config):
    """Create a DatabaseService instance with mock config."""
    return DatabaseService(mock_config)


def test_database_service_init(database_service, mock_config):
    """Test that DatabaseService initializes correctly."""
    assert database_service.config == mock_config
    assert database_service._db is None


@patch("elroy.core.services.database.get_db_manager")
def test_db_manager_lazy_initialization(mock_get_db_manager, database_service):
    """Test that db_manager is lazily initialized."""
    mock_db_manager = MagicMock()
    mock_get_db_manager.return_value = mock_db_manager

    # Access db_manager for the first time
    result = database_service.db_manager

    # Verify that get_db_manager was called
    mock_get_db_manager.assert_called_once_with("sqlite:///test.db")
    assert result == mock_db_manager

    # Access db_manager again
    result2 = database_service.db_manager

    # Verify that get_db_manager was not called again (cached_property)
    assert mock_get_db_manager.call_count == 1
    assert result2 == mock_db_manager


def test_db_property_no_session(database_service):
    """Test that db property raises an error when no session is set."""
    with pytest.raises(ValueError, match="No db session open"):
        _ = database_service.db


def test_db_property_with_session(database_service):
    """Test that db property returns the session when set."""
    mock_session = MagicMock(spec=DbSession)
    database_service.set_db_session(mock_session)

    assert database_service.db == mock_session


def test_set_unset_db_session(database_service):
    """Test setting and unsetting the database session."""
    mock_session = MagicMock(spec=DbSession)

    # Initially not connected
    assert not database_service.is_db_connected()

    # Set session
    database_service.set_db_session(mock_session)
    assert database_service.is_db_connected()
    assert database_service.db == mock_session

    # Unset session
    database_service.unset_db_session()
    assert not database_service.is_db_connected()
    with pytest.raises(ValueError, match="No db session open"):
        _ = database_service.db
