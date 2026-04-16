import types
from inspect import Parameter
from multiprocessing import get_logger
from typing import Any, Union, get_args, get_origin

from toolz import pipe
from toolz.curried import map

logger = get_logger()


def _is_optional(param: Parameter) -> bool:
    origin = get_origin(param.annotation)
    return origin in (Union, types.UnionType) and type(None) in get_args(param.annotation)


def get_casted_value(parameter: Parameter, str_value: str) -> Any | None:
    if not str_value:
        return None
    arg_type = get_args(parameter.annotation)[0] if _is_optional(parameter) else parameter.annotation
    return arg_type(str_value)


def get_prompt_for_param(param: Parameter) -> str:
    prompt_title = pipe(
        param.name,
        lambda x: x.split("_"),
        map(str.capitalize),
        " ".join,
    )

    if _is_optional(param):
        prompt_title += " (optional)"

    return prompt_title + ">"
