"""
Configuration container for ElroyContext.
"""

from types import SimpleNamespace
from typing import Any, Dict


class ElroyConfig:
    """Container for all configuration parameters"""

    def __init__(self, **kwargs):
        # Store all configuration parameters
        self._config = SimpleNamespace(**kwargs)
        # Store original kwargs for direct access
        self._raw_config: Dict[str, Any] = kwargs

    def __getattr__(self, name: str) -> Any:
        # Handle missing attributes gracefully
        return getattr(self._config, name, None)

    @property
    def database_url(self) -> str:
        """Get database URL with proper type."""
        return self._raw_config.get("database_url", "")

    @property
    def system_message_color(self) -> str:
        """Get system message color with proper type."""
        return self._raw_config.get("system_message_color", "")

    @property
    def assistant_color(self) -> str:
        """Get assistant color with proper type."""
        return self._raw_config.get("assistant_color", "")

    @property
    def user_input_color(self) -> str:
        """Get user input color with proper type."""
        return self._raw_config.get("user_input_color", "")

    @property
    def warning_color(self) -> str:
        """Get warning color with proper type."""
        return self._raw_config.get("warning_color", "")

    @property
    def internal_thought_color(self) -> str:
        """Get internal thought color with proper type."""
        return self._raw_config.get("internal_thought_color", "")
