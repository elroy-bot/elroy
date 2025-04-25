"""
Tool service for ElroyContext.
"""

import re
from functools import cached_property

from ...tools.registry import ToolRegistry


class ToolService:
    """Provides access to tools with lazy initialization"""

    def __init__(self, config):
        self.config = config
        self.allowed_shell_command_prefixes = [re.compile(f"^{p}") for p in config.allowed_shell_command_prefixes]

    @cached_property
    def tool_registry(self) -> ToolRegistry:
        registry = ToolRegistry(
            self.config.include_base_tools,
            self.config.custom_tools_path,
            exclude_tools=self.config.exclude_tools,
            shell_commands=self.config.shell_commands,
            allowed_shell_command_prefixes=self.allowed_shell_command_prefixes,
        )
        registry.register_all()
        return registry
