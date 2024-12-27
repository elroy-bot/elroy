import logging
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar("T")


def experimental(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = next((arg for arg in args if hasattr(arg, "io")), None)
        if not ctx:
            ctx = next((value for value in kwargs.values() if hasattr(value, "io")), None)

        if ctx and hasattr(ctx, "io"):
            io = ctx.io
            from ..io.base import ElroyIO

            assert isinstance(io, ElroyIO)
            io.notify_warning("Warning: This is an experimental feature.")
        else:
            logging.warning("No context found to notify of experimental feature.")
        return func(*args, **kwargs)

    return wrapper
