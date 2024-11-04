import logging
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar("T")


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
