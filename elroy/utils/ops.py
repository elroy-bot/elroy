import logging
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, List, Optional, TypeVar

from ..config.config import ElroyContext
from ..system_commands import tail_elroy_logs

T = TypeVar("T")


def is_debug(context: ElroyContext) -> bool:
    return context.config.debug_mode


class AutocompleteParams:
    def active_goal_names(self):
        return ["goal1", "goal2"]

    def active_memory_titles(self):
        return ["memory1", "memory2"]


@dataclass
class ElroyTool:
    context_filter: Callable[[ElroyContext], bool]
    func: Callable[..., Any]
    autocomplete_params: Optional[Callable[..., List[str]]] = None


[ElroyTool(context_filter=is_debug, func=tail_elroy_logs, autocomplete_params=AutocompleteParams.active_goal_names)]


TOOL_MARKER = "_is_tool"
TOOL_MARKER_FUNC = is_debug


def tool(debug_only: bool = False, experimental_only: bool = False):
    """
    Decorator that marks a function as a tool.

    Args:
        debug_only: Whether this tool should only be available in debug mode
        experimental_only: Whether this tool is experimental

    Returns:
        A decorator function that will mark the wrapped function as a tool
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        setattr(wrapper, "debug_only", debug_only)
        setattr(wrapper, "experimental_only", experimental_only)
        return wrapper

    return decorator


def experimental(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        context = next((arg for arg in args if hasattr(arg, "io")), None)
        if not context:
            context = next((value for value in kwargs.values() if hasattr(value, "io")), None)

        if context and hasattr(context, "io"):
            io = context.io
            from ..io.cli import CliIO

            assert isinstance(io, CliIO)
            io.notify_warning("Warning: This is an experimental feature.")
        else:
            logging.warning("No context found to notify of experimental feature.")
        return func(*args, **kwargs)

    return wrapper


@tool(debug_only=True, experimental_only=False)
def debug(value: T) -> T:
    import pdb
    import traceback

    for line in traceback.format_stack():
        print(line.strip())
    pdb.set_trace()
    return value


def debug_log(value: T) -> T:
    import traceback

    traceback.print_stack()
    print(f"CURRENT VALUE: {value}")
    return value
