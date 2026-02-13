import inspect
import json
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path
from re import Pattern
from types import FunctionType, ModuleType
from typing import Any

from toolz import concat, pipe
from toolz.curried import filter, map, remove

from ..core.constants import IS_ENABLED, IS_TOOL
from ..core.logging import get_logger
from .schema import get_function_schema, validate_schema

logger = get_logger()


def is_langchain_tool(func: Callable) -> bool:
    return func.__class__.__name__ == "StructuredTool"


def is_tool(func: Callable) -> bool:
    """Check if a function is marked as a tool by either our @tool decorator or LangChain's."""
    return getattr(func, IS_TOOL, False) or is_langchain_tool(func)


class ToolRegistry:
    def __init__(
        self,
        include_base_tools: bool,
        custom_paths: list[str] | None = None,
        exclude_tools: list[str] | None = None,
        shell_commands: bool = False,
        allowed_shell_command_prefixes: list[Pattern[str]] | None = None,
    ):
        if allowed_shell_command_prefixes is None:
            allowed_shell_command_prefixes = []
        if exclude_tools is None:
            exclude_tools = []
        if custom_paths is None:
            custom_paths = []
        self.include_base_tools = include_base_tools
        self.exclude_tools = exclude_tools
        self.custom_paths = custom_paths
        self.tools = {}
        self._schemas = []
        self.shell_commands = shell_commands
        self.allowed_shell_command_prefixes = allowed_shell_command_prefixes

    def register_all(self):
        if self.include_base_tools:
            from .tools_and_commands import ASSISTANT_VISIBLE_COMMANDS

            for tool in ASSISTANT_VISIBLE_COMMANDS:
                self.register(tool)
        for path in self.custom_paths:
            self.register_path(path)

    def get_schemas(self) -> list[dict[str, Any]]:
        return self._schemas

    def register_path(self, custom_path: str) -> None:
        """
        Load tool functions from a directory, validating their schemas.
        Only loads functions decorated with @tool.

        Args:
            dir: Directory path containing tool Python files

        Returns:
            List of valid tool functions found in the directory
        """
        path = Path(custom_path)
        if not path.exists():
            logger.warning(f"Custom tool path {path} does not exist")
            return

        if path.is_file():
            if path.suffix != ".py":
                logger.warning(f"Custom tool path {path} is not a Python file")
                return
            else:
                file_paths = [path]
        else:
            file_paths = path.glob("*.py")

        pipe(
            file_paths,
            remove(lambda p: p.stem.startswith("_")),
            map(get_module),
            map(get_module_functions),
            concat,
            map(partial(self.register, raise_on_error=False)),
            list,
        )

    def has_non_ctx_args(self, func: Callable) -> bool:
        from ..core.ctx import ElroyContext

        inspect.signature(func)
        return any(param for param in inspect.signature(func).parameters.values() if param.annotation != ElroyContext)

    def register(self, func: Callable, raise_on_error: bool = True) -> None:
        func_name = getattr(func, "__name__", func.__class__.__name__)
        if is_langchain_tool(func):
            func = func.func  # type: ignore
            func_name = getattr(func, "__name__", func.__class__.__name__)
        elif not is_tool(func):
            raise ValueError(f"Function {func_name} is not marked as a tool with @tool decorator")

        if func_name in self.exclude_tools:
            logger.info("Excluding tool: " + func_name)
            return

        if func_name in self.tools:
            raise ValueError(f"Function {func_name} already registered")

        schema = get_function_schema(func)

        errors = validate_schema(schema, self.has_non_ctx_args(func))
        if errors:
            if raise_on_error:
                raise ValueError(f"Invalid schema for function {func_name}:\n{json.dumps(schema)}\n" + "\n".join(errors))
            else:
                logger.warning(f"Invalid schema for function {func_name}:\n" + "\n".join(errors))
        self._schemas.append(schema)
        self.tools[func_name] = func

    def get(self, name: str) -> FunctionType | None:
        return self.tools.get(name)

    def __getitem__(self, name: str) -> FunctionType:
        return self.tools[name]

    def __contains__(self, name: str) -> bool:
        return name in self.tools

    def __len__(self) -> int:
        return len(self.tools)


def get_module(file_path: Path) -> ModuleType:
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if not spec or not spec.loader:
            raise ValueError(f"Failed to import {file_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        raise ValueError(f"Failed to import {file_path}: {str(e)}") from e


def get_module_functions(module: ModuleType) -> Iterator[FunctionType]:
    return pipe(
        dir(module),
        map(lambda name: getattr(module, name)),
        filter(inspect.isfunction),
        filter(is_tool),
        filter(lambda _: _.__module__ == module.__name__),
    )


def get_system_tool_schemas() -> list[dict[str, Any]]:
    from .tools_and_commands import ASSISTANT_VISIBLE_COMMANDS

    return pipe(
        ASSISTANT_VISIBLE_COMMANDS,
        filter(lambda f: getattr(f, IS_ENABLED, True)),
        map(get_function_schema),
        list,
    )


def do_not_use() -> str:
    """This is a dummy function that should not be used. It is only for testing purposes.

    Returns:
        str: A message indicating that this function should not be used
    """
    return "This function should not be used."
