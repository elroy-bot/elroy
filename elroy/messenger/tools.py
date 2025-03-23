import traceback

from toolz import merge, pipe

from ..core.constants import RecoverableToolError
from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..db.db_models import FunctionCall
from ..llm.stream_parser import (
    AssistantToolResult,
)

logger = get_logger()


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
