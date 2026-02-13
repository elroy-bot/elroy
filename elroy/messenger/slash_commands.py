from collections.abc import Iterator
from inspect import signature

from toolz import pipe
from toolz.curried import valfilter

from ..cli.slash_commands import get_casted_value, get_prompt_for_param
from ..core.constants import RecoverableToolError
from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..core.tracing import tracer
from ..io.cli import CliIO
from ..llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    AssistantToolResult,
)
from ..tools.tools_and_commands import USER_ONLY_COMMANDS, get_help

logger = get_logger()


@tracer.chain
def invoke_slash_command(
    io: CliIO, ctx: ElroyContext, msg: str
) -> str | Iterator[AssistantResponse | AssistantInternalThought | AssistantToolResult]:
    """
    Takes user input and executes a system command. For commands with a single non-context argument,
    executes directly with provided argument. For multi-argument commands, prompts for each argument.
    """
    if msg.startswith("/"):
        msg = msg[1:]

    command = msg.split(" ")[0]
    input_arg = " ".join(msg.split(" ")[1:])

    if command == "help":
        func = get_help
    else:
        func = ctx.tool_registry.tools.get(command) or next((f for f in USER_ONLY_COMMANDS if f.__name__ == command), None)

    try:
        if not func:
            raise RecoverableToolError(f"Invalid command: {command}. Use /help for a list of valid commands")

        params = list(signature(func).parameters.values())

        # Count non-context parameters
        non_ctx_params = [p for p in params if p.annotation != ElroyContext]

        func_args = {}

        # If exactly one non-context parameter and we have input, execute directly
        if len(non_ctx_params) == 1 and input_arg:
            func_args["ctx"] = ctx
            func_args[non_ctx_params[0].name] = get_casted_value(non_ctx_params[0], input_arg)
            return pipe(
                func_args,
                valfilter(lambda _: _ is not None and _ != ""),
                lambda _: func(**_),
            )

        # Otherwise, fall back to interactive parameter collection
        input_used = False
        for param in params:
            if param.annotation == ElroyContext:
                func_args[param.name] = ctx
            elif input_arg and not input_used:
                argument = io.prompt_user(ctx.thread_pool, 0, get_prompt_for_param(param), prefill=input_arg)
                func_args[param.name] = get_casted_value(param, argument)
                input_used = True
            elif input_used or not input_arg:
                argument = io.prompt_user(ctx.thread_pool, 0, get_prompt_for_param(param))
                func_args[param.name] = get_casted_value(param, argument)

        return pipe(
            func_args,
            valfilter(lambda _: _ is not None and _ != ""),
            lambda _: func(**_),
        )
    except RecoverableToolError as e:
        return str(e)
    except EOFError:
        return "Cancelled."
