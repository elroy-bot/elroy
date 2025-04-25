from unittest.mock import MagicMock

import pytest

from elroy.core.config import ElroyConfig
from elroy.core.services.database import DatabaseService
from elroy.core.services.llm import LLMService
from elroy.core.services.memory import MemoryService
from elroy.core.services.tools import ToolService
from elroy.core.services.user import UserService


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return ElroyConfig(
        database_url="sqlite:///test.db",
        user_token="test-user-token",
        chat_model="gpt-4",
        embedding_model="text-embedding-ada-002",
        embedding_model_size=1536,
        max_context_age_minutes=60,
        min_convo_age_for_greeting_minutes=30,
        include_base_tools=True,
        custom_tools_path=["custom/tools/path"],
        exclude_tools=["excluded_tool"],
        shell_commands=True,
        allowed_shell_command_prefixes=["ls", "cat"],
    )


@pytest.fixture
def mock_db_service():
    """Create a mock database service."""
    db_service = MagicMock(spec=DatabaseService)
    mock_db = MagicMock()
    db_service.db = mock_db
    return db_service


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    llm_service = MagicMock(spec=LLMService)
    mock_chat_model = MagicMock()
    mock_embedding_model = MagicMock()
    llm_service.chat_model = mock_chat_model
    llm_service.embedding_model = mock_embedding_model
    llm_service.is_chat_model_inferred = False
    return llm_service


@pytest.fixture
def mock_tool_service():
    """Create a mock tool service."""
    tool_service = MagicMock(spec=ToolService)
    mock_tool_registry = MagicMock()
    tool_service.tool_registry = mock_tool_registry
    return tool_service


@pytest.fixture
def mock_user_service():
    """Create a mock user service."""
    user_service = MagicMock(spec=UserService)
    user_service.user_id = 123
    return user_service


@pytest.fixture
def mock_memory_service():
    """Create a mock memory service."""
    from datetime import timedelta

    memory_service = MagicMock(spec=MemoryService)
    memory_service.max_in_context_message_age = timedelta(minutes=60)
    memory_service.min_convo_age_for_greeting = timedelta(minutes=30)
    return memory_service


@pytest.fixture
def database_service(mock_config):
    """Create a real DatabaseService instance with mock config."""
    return DatabaseService(mock_config)


@pytest.fixture
def llm_service(mock_config):
    """Create a real LLMService instance with mock config."""
    return LLMService(mock_config)


@pytest.fixture
def tool_service(mock_config):
    """Create a real ToolService instance with mock config."""
    return ToolService(mock_config)


@pytest.fixture
def user_service(mock_config, mock_db_service):
    """Create a real UserService instance with mock config and db service."""
    return UserService(mock_config, mock_db_service)


@pytest.fixture
def memory_service(mock_config):
    """Create a real MemoryService instance with mock config."""
    return MemoryService(mock_config)
