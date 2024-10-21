import inspect
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar("T")


def experimental(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        context = next((arg for arg in args if hasattr(arg, "console")), None)
        if not context:
            context = next((value for value in kwargs.values() if hasattr(value, "console")), None)
        if context and hasattr(context, "console"):
            context.console.print("[yellow]Warning: This is an experimental feature.[/yellow]")
            context.console.print("[yellow]Please provide feedback at https://github.com/elroy-bot/elroy/issues[/yellow]")
        return func(*args, **kwargs)

    return wrapper


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


def get_missing_arguments(func):
    signature = inspect.signature(func.func)
    bound = signature.bind_partial(**func.keywords)
    missing_args = [param_name for param_name, param in signature.parameters.items() if param_name not in bound.arguments]
    return missing_args
