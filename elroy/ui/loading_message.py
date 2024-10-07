import functools
from typing import Any, Callable

from rich.console import Console


def cli_loading(message: str = "Loading..."):
    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            console = Console()
            with console.status(message, spinner="dots") as status:
                result = func(*args, **kwargs)
            return result

        return wrapper

    return decorator
