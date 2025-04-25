import re
from unittest.mock import MagicMock, patch

import pytest

from elroy.core.config import ElroyConfig
from elroy.core.services.tools import ToolService


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return ElroyConfig(
        include_base_tools=True,
        custom_tools_path=["custom/tools/path"],
        exclude_tools=["excluded_tool"],
        shell_commands=True,
        allowed_shell_command_prefixes=["ls", "cat"],
    )


@pytest.fixture
def tool_service(mock_config):
    """Create a ToolService instance with mock config."""
    return ToolService(mock_config)


def test_tool_service_init(tool_service, mock_config):
    """Test that ToolService initializes correctly."""
    assert tool_service.config == mock_config
    assert len(tool_service.allowed_shell_command_prefixes) == 2
    assert all(isinstance(pattern, re.Pattern) for pattern in tool_service.allowed_shell_command_prefixes)
    assert tool_service.allowed_shell_command_prefixes[0].pattern == "^ls"
    assert tool_service.allowed_shell_command_prefixes[1].pattern == "^cat"


@patch("elroy.core.services.tools.ToolRegistry")
def test_tool_registry_lazy_initialization(MockToolRegistry, tool_service):
    """Test that tool_registry is lazily initialized."""
    mock_registry = MagicMock()
    MockToolRegistry.return_value = mock_registry

    # Access tool_registry for the first time
    result = tool_service.tool_registry

    # Verify that ToolRegistry was instantiated with correct parameters
    MockToolRegistry.assert_called_once_with(
        True,  # include_base_tools
        ["custom/tools/path"],  # custom_tools_path
        exclude_tools=["excluded_tool"],
        shell_commands=True,
        allowed_shell_command_prefixes=tool_service.allowed_shell_command_prefixes,
    )

    # Verify that register_all was called
    mock_registry.register_all.assert_called_once()

    assert result == mock_registry

    # Access tool_registry again
    result2 = tool_service.tool_registry

    # Verify that ToolRegistry was not instantiated again (cached_property)
    assert MockToolRegistry.call_count == 1
    assert result2 == mock_registry
