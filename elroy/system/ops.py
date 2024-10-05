import inspect
from typing import TypeVar

T = TypeVar("T")


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
