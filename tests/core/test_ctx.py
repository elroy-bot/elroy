from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from elroy.core.config import ElroyConfig
from elroy.core.ctx import ElroyContext


@pytest.fixture
def mock_params():
    """Create mock parameters for ElroyContext."""
    return {
        "database_url": "sqlite:///test.db",
        "show_internal_thought": True,
        "system_message_color": "blue",
        "assistant_color": "green",
        "user_input_color": "yellow",
        "warning_color": "red",
        "internal_thought_color": "magenta",
        "user_token": "test-user-token",
        "embedding_model": "text-embedding-ada-002",
        "embedding_model_size": 1536,
        "max_assistant_loops": 10,
        "max_tokens": 4000,
        "max_context_age_minutes": 60,
        "min_convo_age_for_greeting_minutes": 30,
        "memory_cluster_similarity_threshold": 0.8,
        "max_memory_cluster_size": 10,
        "min_memory_cluster_size": 3,
        "memories_between_consolidation": 5,
        "messages_between_memory": 3,
        "l2_memory_relevance_distance_threshold": 0.7,
        "debug": False,
        "default_assistant_name": "Elroy",
        "use_background_threads": False,
        "max_ingested_doc_lines": 1000,
        "include_base_tools": True,
        "reflect": False,
        "shell_commands": True,
        "allowed_shell_command_prefixes": ["ls", "cat"],
    }


@pytest.fixture
def ctx(mock_params):
    """Create an ElroyContext instance with mock parameters."""
    return ElroyContext(**mock_params)


def test_elroy_context_init(ctx, mock_params):
    """Test that ElroyContext initializes correctly."""
    # Test that config is initialized
    assert isinstance(ctx.config, ElroyConfig)

    # Test that top-level attributes are set correctly
    assert ctx.user_token == mock_params["user_token"]
    assert ctx.show_internal_thought == mock_params["show_internal_thought"]
    assert ctx.default_assistant_name == mock_params["default_assistant_name"]
    assert ctx.debug == mock_params["debug"]
    assert ctx.max_tokens == mock_params["max_tokens"]
    assert ctx.max_assistant_loops == mock_params["max_assistant_loops"]
    assert ctx.l2_memory_relevance_distance_threshold == mock_params["l2_memory_relevance_distance_threshold"]
    assert ctx.context_refresh_target_tokens == int(mock_params["max_tokens"] / 3)

    # Test that service references are initialized to None
    assert ctx._db_service is None
    assert ctx._llm_service is None
    assert ctx._tool_service is None
    assert ctx._user_service is None
    assert ctx._memory_service is None
    assert ctx._thread_pool is None


@patch("elroy.core.ctx.DatabaseService")
def test_db_service_lazy_initialization(MockDatabaseService, ctx):
    """Test that db_service is lazily initialized."""
    mock_service = MagicMock()
    MockDatabaseService.return_value = mock_service

    # Access db_service for the first time
    result = ctx.db_service

    # Verify that DatabaseService was instantiated with correct parameters
    MockDatabaseService.assert_called_once_with(ctx.config)
    assert result == mock_service

    # Access db_service again
    result2 = ctx.db_service

    # Verify that DatabaseService was not instantiated again (cached_property)
    assert MockDatabaseService.call_count == 1
    assert result2 == mock_service


@patch("elroy.core.ctx.LLMService")
def test_llm_service_lazy_initialization(MockLLMService, ctx):
    """Test that llm_service is lazily initialized."""
    mock_service = MagicMock()
    MockLLMService.return_value = mock_service

    # Access llm_service for the first time
    result = ctx.llm_service

    # Verify that LLMService was instantiated with correct parameters
    MockLLMService.assert_called_once_with(ctx.config)
    assert result == mock_service


@patch("elroy.core.ctx.ToolService")
def test_tool_service_lazy_initialization(MockToolService, ctx):
    """Test that tool_service is lazily initialized."""
    mock_service = MagicMock()
    MockToolService.return_value = mock_service

    # Access tool_service for the first time
    result = ctx.tool_service

    # Verify that ToolService was instantiated with correct parameters
    MockToolService.assert_called_once_with(ctx.config)
    assert result == mock_service


@patch("elroy.core.ctx.UserService")
def test_user_service_lazy_initialization(MockUserService, ctx):
    """Test that user_service is lazily initialized."""
    mock_service = MagicMock()
    MockUserService.return_value = mock_service

    # First, mock the db_service
    mock_db_service = MagicMock()
    ctx._db_service = mock_db_service

    # Access user_service for the first time
    result = ctx.user_service

    # Verify that UserService was instantiated with correct parameters
    MockUserService.assert_called_once_with(ctx.config, mock_db_service)
    assert result == mock_service


@patch("elroy.core.ctx.MemoryService")
def test_memory_service_lazy_initialization(MockMemoryService, ctx):
    """Test that memory_service is lazily initialized."""
    mock_service = MagicMock()
    MockMemoryService.return_value = mock_service

    # Access memory_service for the first time
    result = ctx.memory_service

    # Verify that MemoryService was instantiated with correct parameters
    MockMemoryService.assert_called_once_with(ctx.config)
    assert result == mock_service


def test_thread_pool_lazy_initialization(ctx):
    """Test that thread_pool is lazily initialized."""
    # Access thread_pool for the first time
    result = ctx.thread_pool

    # Verify that thread_pool is a ThreadPoolExecutor
    assert isinstance(result, ThreadPoolExecutor)

    # Access thread_pool again
    result2 = ctx.thread_pool

    # Verify that it's the same instance
    assert result2 is result


def test_config_path_lazy_initialization(ctx):
    """Test that config_path is lazily initialized."""
    # Create a new context with a specific config_path
    config = ElroyConfig(config_path="/path/to/config.yml")
    ctx = ElroyContext(
        database_url="sqlite:///test.db",
        show_internal_thought=True,
        system_message_color="blue",
        assistant_color="green",
        user_input_color="yellow",
        warning_color="red",
        internal_thought_color="magenta",
        user_token="test-user-token",
        embedding_model="text-embedding-ada-002",
        embedding_model_size=1536,
        max_assistant_loops=10,
        max_tokens=4000,
        max_context_age_minutes=60,
        min_convo_age_for_greeting_minutes=30,
        memory_cluster_similarity_threshold=0.8,
        max_memory_cluster_size=10,
        min_memory_cluster_size=3,
        memories_between_consolidation=5,
        messages_between_memory=3,
        l2_memory_relevance_distance_threshold=0.7,
        debug=False,
        default_assistant_name="Elroy",
        use_background_threads=False,
        max_ingested_doc_lines=1000,
        include_base_tools=True,
        reflect=False,
        shell_commands=True,
        allowed_shell_command_prefixes=["ls", "cat"],
        config_path="/path/to/config.yml",
    )

    # Access config_path for the first time
    result = ctx.config_path

    # Verify that config_path is a Path
    assert isinstance(result, Path)
    assert result == Path("/path/to/config.yml")


@patch("elroy.core.ctx.get_default_config_path")
def test_config_path_default(mock_get_default_config_path, ctx):
    """Test that config_path uses default when not specified."""
    mock_path = Path("/default/config/path")
    mock_get_default_config_path.return_value = mock_path

    # Ensure config_path is not set
    ctx.config._raw_config.pop("config_path", None)

    # Access config_path for the first time
    result = ctx.config_path

    # Verify that get_default_config_path was called
    mock_get_default_config_path.assert_called_once()
    assert result == mock_path


def test_db_property_delegation(ctx):
    """Test that db property delegates to db_service."""
    mock_db = MagicMock()
    mock_db_service = MagicMock()
    mock_db_service.db = mock_db
    ctx._db_service = mock_db_service

    assert ctx.db == mock_db


def test_db_manager_property_delegation(ctx):
    """Test that db_manager property delegates to db_service."""
    mock_db_manager = MagicMock()
    mock_db_service = MagicMock()
    mock_db_service.db_manager = mock_db_manager
    ctx._db_service = mock_db_service

    assert ctx.db_manager == mock_db_manager


def test_is_chat_model_inferred_property_delegation(ctx):
    """Test that is_chat_model_inferred property delegates to llm_service."""
    mock_llm_service = MagicMock()
    mock_llm_service.is_chat_model_inferred = True
    ctx._llm_service = mock_llm_service

    assert ctx.is_chat_model_inferred is True


def test_chat_model_property_delegation(ctx):
    """Test that chat_model property delegates to llm_service."""
    mock_chat_model = MagicMock()
    mock_llm_service = MagicMock()
    mock_llm_service.chat_model = mock_chat_model
    ctx._llm_service = mock_llm_service

    assert ctx.chat_model == mock_chat_model


def test_embedding_model_property_delegation(ctx):
    """Test that embedding_model property delegates to llm_service."""
    mock_embedding_model = MagicMock()
    mock_llm_service = MagicMock()
    mock_llm_service.embedding_model = mock_embedding_model
    ctx._llm_service = mock_llm_service

    assert ctx.embedding_model == mock_embedding_model


def test_tool_registry_property_delegation(ctx):
    """Test that tool_registry property delegates to tool_service."""
    mock_tool_registry = MagicMock()
    mock_tool_service = MagicMock()
    mock_tool_service.tool_registry = mock_tool_registry
    ctx._tool_service = mock_tool_service

    assert ctx.tool_registry == mock_tool_registry


def test_user_id_property_delegation(ctx):
    """Test that user_id property delegates to user_service."""
    mock_user_service = MagicMock()
    mock_user_service.user_id = 123
    ctx._user_service = mock_user_service

    assert ctx.user_id == 123


def test_max_in_context_message_age_property_delegation(ctx):
    """Test that max_in_context_message_age property delegates to memory_service."""
    from datetime import timedelta

    mock_timedelta = timedelta(minutes=60)
    mock_memory_service = MagicMock()
    mock_memory_service.max_in_context_message_age = mock_timedelta
    ctx._memory_service = mock_memory_service

    assert ctx.max_in_context_message_age == mock_timedelta


def test_min_convo_age_for_greeting_property_delegation(ctx):
    """Test that min_convo_age_for_greeting property delegates to memory_service."""
    from datetime import timedelta

    mock_timedelta = timedelta(minutes=30)
    mock_memory_service = MagicMock()
    mock_memory_service.min_convo_age_for_greeting = mock_timedelta
    ctx._memory_service = mock_memory_service

    assert ctx.min_convo_age_for_greeting == mock_timedelta


def test_is_db_connected_method_delegation(ctx):
    """Test that is_db_connected method delegates to db_service."""
    mock_db_service = MagicMock()
    mock_db_service.is_db_connected.return_value = True
    ctx._db_service = mock_db_service

    assert ctx.is_db_connected() is True
    mock_db_service.is_db_connected.assert_called_once()


def test_set_db_session_method_delegation(ctx):
    """Test that set_db_session method delegates to db_service."""
    mock_db = MagicMock()
    mock_db_service = MagicMock()
    ctx._db_service = mock_db_service

    ctx.set_db_session(mock_db)

    # Verify that _db is set for backward compatibility
    assert ctx._db == mock_db

    # Verify that set_db_session was called on db_service
    mock_db_service.set_db_session.assert_called_once_with(mock_db)


def test_unset_db_session_method_delegation(ctx):
    """Test that unset_db_session method delegates to db_service."""
    mock_db_service = MagicMock()
    ctx._db_service = mock_db_service
    ctx._db = MagicMock()  # Set a mock db

    ctx.unset_db_session()

    # Verify that _db is set to None for backward compatibility
    assert ctx._db is None

    # Verify that unset_db_session was called on db_service
    mock_db_service.unset_db_session.assert_called_once()
