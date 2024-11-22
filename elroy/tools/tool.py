from functools import wraps
from inspect import signature
from typing import Callable, TypeVar, ParamSpec

from ..config.config import ElroyContext

P = ParamSpec('P')
R = TypeVar('R')


def only_in_debug(context: ElroyContext):
    return context.config.debug_mode


def tool(func: Callable[P, R]) -> Callable[P, R]:
    """
    Decorator that validates the function has ElroyContext as its first parameter.
    
    Args:
        func: The function to decorate
        
    Returns:
        The decorated function
        
    Raises:
        ValueError: If the first parameter is not of type ElroyContext
    """
    sig = signature(func)
    params = list(sig.parameters.values())
    
    if not params:
        raise ValueError(f"Tool function {func.__name__} must have at least one parameter (ElroyContext)")
        
    first_param = params[0]
    if first_param.annotation != ElroyContext:
        raise ValueError(f"First parameter of {func.__name__} must be ElroyContext, got {first_param.annotation}")

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return func(*args, **kwargs)

    return wrapper


@tool
def example_debug_tool(context: ElroyContext):
    if only_in_debug(context):
        print("This is a debug tool")
    else:
        print("This is not a debug tool")
