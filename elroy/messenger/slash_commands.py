from collections.abc import Iterator
from inspect import signature

from toolz import pipe
from toolz.curried import valfilter

from ..cli.slash_commands import get_casted_value, get_prompt_for_param
from ..core.constants import RecoverableToolError
from ..core.ctx import ElroyConfig
from ..core.logging import get_logger
from ..core.runtime import CommandRuntime, build_command_runtime
from ..core.session import invoke_with_config
from ..core.turn import TurnContext
from ..io.base import ElroyIO
from ..llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    AssistantToolResult,
)
from ..tools.tools_and_commands import USER_ONLY_COMMANDS, do_get_help, get_help

logger = get_logger()


def _is_context_param(param) -> bool:
    return param.annotation in {ElroyConfig, TurnContext}


def _get_slash_command_func(runtime: CommandRuntime, command: str):
    if command == "help":

        def _help():
            return do_get_help(runtime)

        _help.__name__ = get_help.__name__
        _help.__doc__ = get_help.__doc__
        return _help
    return runtime.tool_registry.tools.get(command) or next((f for f in USER_ONLY_COMMANDS if f.__name__ == command), None)


def do_invoke_slash_command(
    io: ElroyIO, runtime: CommandRuntime, ctx: ElroyConfig, msg: str
) -> str | Iterator[AssistantResponse | AssistantInternalThought | AssistantToolResult]:
    msg = msg.removeprefix("/")

    command = msg.split(" ")[0]
    input_arg = " ".join(msg.split(" ")[1:])

    func = _get_slash_command_func(runtime, command)

    try:
        if not func:
            raise RecoverableToolError(f"Invalid command: {command}. Use /help for a list of valid commands")

        params = list(signature(func).parameters.values())
        non_ctx_params = [p for p in params if not _is_context_param(p)]
        func_args = {}

        if len(non_ctx_params) == 1 and input_arg:
            func_args[non_ctx_params[0].name] = get_casted_value(non_ctx_params[0], input_arg)
            return pipe(
                func_args,
                valfilter(lambda _: _ is not None and _ != ""),
                lambda _: invoke_with_config(func, ctx, **_),
            )

        input_used = False
        for param in params:
            if _is_context_param(param):
                continue
            if input_arg and not input_used:
                argument = io.prompt_user(runtime.thread_pool, 0, get_prompt_for_param(param), prefill=input_arg)
                func_args[param.name] = get_casted_value(param, argument)
                input_used = True
            elif input_used or not input_arg:
                argument = io.prompt_user(runtime.thread_pool, 0, get_prompt_for_param(param))
                func_args[param.name] = get_casted_value(param, argument)

        return pipe(
            func_args,
            valfilter(lambda _: _ is not None and _ != ""),
            lambda _: invoke_with_config(func, ctx, **_),
        )
    except RecoverableToolError as e:
        return str(e)
    except EOFError:
        return "Cancelled."


def invoke_slash_command(
    io: ElroyIO, ctx: ElroyConfig, msg: str
) -> str | Iterator[AssistantResponse | AssistantInternalThought | AssistantToolResult]:
    """
    Takes user input and executes a system command. For commands with a single non-context argument,
    executes directly with provided argument. For multi-argument commands, prompts for each argument.
    """
    return do_invoke_slash_command(io, build_command_runtime(ctx), ctx, msg)
