from __future__ import annotations

from pathlib import Path
from types import ModuleType

from ..core.logging import get_logger
from ..tools.registry import get_module
from .plugin import ELROY_PLUGIN_ATTR, ElroyPlugin

logger = get_logger()


class PluginRegistry:
    def __init__(self) -> None:
        self.plugins: list[ElroyPlugin] = []

    def register_path(self, path_str: str) -> None:
        path = Path(path_str)
        if not path.exists():
            logger.warning(f"Plugin path {path} does not exist")
            return

        file_paths = [path] if path.is_file() else list(path.glob("*.py"))

        for file_path in file_paths:
            if file_path.stem.startswith("_") or file_path.suffix != ".py":
                continue
            try:
                module = get_module(file_path)
                self._register_from_module(module)
            except Exception as exc:
                logger.warning(f"Failed to load plugin from {file_path}: {exc}")

    def _register_from_module(self, module: ModuleType) -> None:
        plugin = getattr(module, ELROY_PLUGIN_ATTR, None)
        if plugin is None:
            return
        if not isinstance(plugin, ElroyPlugin):
            logger.warning(f"Module {module.__name__!r} has {ELROY_PLUGIN_ATTR} but it is not an ElroyPlugin instance")
            return
        if any(p.name == plugin.name for p in self.plugins):
            logger.warning(f"Plugin {plugin.name!r} already registered — skipping duplicate from {module.__name__!r}")
            return
        self.plugins.append(plugin)
        logger.info(f"Registered plugin: {plugin.name!r}")

    @classmethod
    def from_path(cls, path: str | None) -> PluginRegistry:
        registry = cls()
        if path:
            registry.register_path(path)
        return registry
