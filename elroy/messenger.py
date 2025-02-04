import traceback
from functools import partial
from inspect import signature
from typing import Iterator, List, Optional, Union

from toolz import merge, pipe
from toolz.curried import valfilter

from .cli.slash_commands import _get_casted_value, _get_prompt_for_param
from .config.constants import ASSISTANT, SYSTEM, TOOL, USER, RecoverableToolError
from .config.ctx import ElroyContext
from .db.db_models import FunctionCall
from .io.cli import CliIO
from .llm.client import generate_chat_completion_message
from .llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    AssistantToolResult,
    CodeBlock,
)
from .repository.context_messages.data_models import ContextMessage
from .repository.context_messages.operations import add_context_messages
from .repository.context_messages.queries import get_context_messages
from .repository.context_messages.validations import validate
from .repository.memories.queries import get_relevant_memories
from .tools.tools_and_commands import SYSTEM_COMMANDS


def process_message(
    role: str, ctx: ElroyContext, msg: str, force_tool: Optional[str] = None
) -> Iterator[Union[AssistantResponse, AssistantInternalThought, CodeBlock, AssistantToolResult, FunctionCall]]:
    assert role in [USER, ASSISTANT, SYSTEM]

    context_messages = pipe(
        get_context_messages(ctx),
        partial(validate, ctx),
        list,
    )

    new_msgs = [ContextMessage(role=role, content=msg, chat_model=None)]
    new_msgs += get_relevant_memories(ctx, context_messages + new_msgs)

    loops = 0
    while True:
        # new_msgs accumulates across all loops, so we can only store new messages once
        # tool_context_messages and function_calls reset each loop: we need to keep track so we can determine whether we need to continue looping
        function_calls: List[FunctionCall] = []
        tool_context_messages: List[ContextMessage] = []

        stream = generate_chat_completion_message(
            chat_model=ctx.chat_model,
            context_messages=context_messages + new_msgs,
            tool_schemas=ctx.tool_registry.get_schemas(),
            enable_tools=(not ctx.chat_model.inline_tool_calls) and loops <= ctx.max_assistant_loops,
            force_tool=force_tool,
        )
        for stream_chunk in stream.process_stream():
            if isinstance(stream_chunk, (AssistantResponse, AssistantInternalThought, CodeBlock)):
                yield stream_chunk
            elif isinstance(stream_chunk, FunctionCall):
                yield stream_chunk  # yield the call

                function_calls.append(stream_chunk)
                tool_call_result = exec_function_call(ctx, stream_chunk)
                tool_context_messages.append(
                    ContextMessage(
                        role=TOOL,
                        tool_call_id=stream_chunk.id,
                        content=tool_call_result.content,
                        chat_model=ctx.chat_model.name,
                    )
                )

                yield tool_call_result

        new_msgs.append(
            ContextMessage(
                role=ASSISTANT,
                content=stream.get_full_text(),
                tool_calls=(None if not function_calls else [f.to_tool_call() for f in function_calls]),
                chat_model=ctx.chat_model.name,
            )
        )

        new_msgs += tool_context_messages
        if force_tool:
            assert tool_context_messages, "force_tool set, but no tool messages generated"
            add_context_messages(ctx, new_msgs)
            break  # we are specifically requesting tool call results, so don't need to loop for assistant response
        elif tool_context_messages:
            # do NOT persist context messages with add_context_messages at this point, we are continuing to loop and accumulate new msgs
            loops += 1
        else:
            add_context_messages(ctx, new_msgs)
            break


def exec_function_call(ctx: ElroyContext, function_call: FunctionCall) -> AssistantToolResult:
    function_to_call = ctx.tool_registry.get(function_call.function_name)
    if not function_to_call:
        return AssistantToolResult(f"Function {function_call.function_name} not found", True)

    error_msg_prefix = f"Error invoking tool {function_call.function_name}:"  # hopefully we don't need this!

    try:
        return pipe(
            {"ctx": ctx} if "ctx" in function_to_call.__code__.co_varnames else {},
            lambda d: merge(function_call.arguments, d),
            lambda args: function_to_call.__call__(**args),
            lambda result: str(result) if result is not None else "Success",
            lambda result: AssistantToolResult(result),
        )  # type: ignore

    except RecoverableToolError as e:
        return AssistantToolResult(f"{error_msg_prefix} {e}", True)

    except Exception as e:
        return AssistantToolResult(
            f"{error_msg_prefix}:\n{function_call}\n\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__)),
            True,
        )


async def invoke_slash_command(
    io: CliIO, ctx: ElroyContext, msg: str
) -> Union[str, Iterator[Union[AssistantResponse, AssistantInternalThought, AssistantToolResult]]]:
    """
    Takes user input and executes a system command. For commands with a single non-context argument,
    executes directly with provided argument. For multi-argument commands, prompts for each argument.
    """
    if msg.startswith("/"):
        msg = msg[1:]

    command = msg.split(" ")[0]
    input_arg = " ".join(msg.split(" ")[1:])

    func = next((f for f in SYSTEM_COMMANDS if f.__name__ == command), None)

    if not func:
        raise RecoverableToolError(f"Invalid command: {command}. Use /help for a list of valid commands")

    params = list(signature(func).parameters.values())

    # Count non-context parameters
    non_ctx_params = [p for p in params if p.annotation != ElroyContext]

    func_args = {}

    # If exactly one non-context parameter and we have input, execute directly
    if len(non_ctx_params) == 1 and input_arg:
        func_args["ctx"] = ctx
        func_args[non_ctx_params[0].name] = _get_casted_value(non_ctx_params[0], input_arg)
        return pipe(
            func_args,
            valfilter(lambda _: _ is not None and _ != ""),
            lambda _: func(**_),
        )  # type: ignore

    # Otherwise, fall back to interactive parameter collection
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
