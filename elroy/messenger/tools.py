import traceback

from pydantic import BaseModel
from toolz import merge, pipe

from ..core.constants import RecoverableToolError
from ..core.ctx import ElroyConfig
from ..core.logging import get_logger
from ..core.runtime import build_tool_execution_runtime
from ..core.turn import TurnContext
from ..db.db_models import FunctionCall
from ..llm.stream_parser import AssistantToolResult

logger = get_logger()


def _build_injected_args(turn: TurnContext, function_to_call) -> dict:
    injected_args = {}
    if "ctx" in function_to_call.__code__.co_varnames:
        injected_args["ctx"] = turn.config
    for param in function_to_call.__signature__.parameters.values() if hasattr(function_to_call, "__signature__") else []:
        if param.annotation == TurnContext:
            injected_args[param.name] = turn
        elif param.annotation == ElroyConfig:
            injected_args[param.name] = turn.config
    return injected_args


def exec_function_call(turn: TurnContext, function_call: FunctionCall) -> BaseModel:
    runtime = build_tool_execution_runtime(turn)
    function_to_call = runtime.tool_registry.get(function_call.function_name)
    if not function_to_call:
        logger.debug(f"Function {function_call.function_name} not found in tool registry, treating as no-op")
        return AssistantToolResult(content="OK", is_error=False)

    error_msg_prefix = f"Error invoking tool {function_call.function_name}:"  # hopefully we don't need this!

    try:
        injected_args = _build_injected_args(turn, function_to_call)
        return pipe(
            injected_args,
            lambda d: merge(function_call.arguments, d),
            lambda args: function_to_call.__call__(**args),
            lambda result: "Success" if result is None else result,
            lambda result: result if isinstance(result, BaseModel) else AssistantToolResult(content=str(result)),
        )

    except RecoverableToolError as e:
        return AssistantToolResult(content=f"{error_msg_prefix} {e}", is_error=True)

    except Exception as e:
        return AssistantToolResult(
            content=f"{error_msg_prefix}:\n{function_call}\n\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__)),
            is_error=True,
        )
