from inspect import Parameter, signature
from typing import Any, Optional, Union, get_args, get_origin

from toolz import pipe
from toolz.curried import map, valfilter

from ..config.ctx import ElroyContext
from ..io.cli import CliIO
from ..system_commands import SYSTEM_COMMANDS


async def invoke_system_command(ctx: ElroyContext, msg: str) -> str:
    """
    Takes user input and executes a system command

    Currently only works well for commands that take 1 non-context argument

    In the future, the execute system command should surface a form
    """
    io = ctx.io
    assert isinstance(io, CliIO)
    if msg.startswith("/"):
        msg = msg[1:]

    command = msg.split(" ")[0]
    input_arg = " ".join(msg.split(" ")[1:])

    func = next((f for f in SYSTEM_COMMANDS if f.__name__ == command), None)

    if not func:
        return f"Unknown command: {command}. Valid options are: {', '.join([f.__name__ for f in SYSTEM_COMMANDS])}"

    params = list(signature(func).parameters.values())

    func_args = {}

    input_used = False
    for param in params:
        if param.annotation == ElroyContext:
            func_args[param.name] = ctx
        elif input_arg and not input_used:
            argument = await io.prompt_user(_get_prompt_for_param(param), prefill=input_arg)
            func_args[param.name] = _get_casted_value(param, argument)
            input_used = True
        elif input_used or not input_arg:
            argument = await io.prompt_user(_get_prompt_for_param(param))
            func_args[param.name] = _get_casted_value(param, argument)

    return pipe(
        func_args,
        valfilter(lambda _: _ is not None and _ != ""),
        lambda _: func(**_),
    )  # type: ignore


def _is_optional(param: Parameter) -> bool:
    return get_origin(param.annotation) is Union and type(None) in get_args(param.annotation)


def _get_casted_value(parameter: Parameter, str_value: str) -> Optional[Any]:
    if not str_value:
        return None
    # detect if it is union
    if _is_optional(parameter):
        arg_type = get_args(parameter.annotation)[0]
    else:
        arg_type = parameter.annotation
    return arg_type(str_value)


def _get_prompt_for_param(param: Parameter) -> str:
    prompt_title = pipe(
        param.name,
        lambda x: x.split("_"),
        map(str.capitalize),
        " ".join,
    )

    if _is_optional(param):
        prompt_title += " (optional)"

    return prompt_title + ">"
