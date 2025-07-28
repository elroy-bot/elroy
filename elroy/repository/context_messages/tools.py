import uuid
from typing import List, Union

from pydantic import BaseModel

from ...core.constants import ASSISTANT, TOOL, tool
from ...core.ctx import ElroyContext
from ...db.db_models import Memory, ToolCall
from .data_models import ContextMessage


def to_synthetic_tool_call(func_name: str, func_response: Union[str, BaseModel]) -> List[ContextMessage]:
    tool_call_id = str(uuid.uuid4())

    return [
        ContextMessage(
            role=ASSISTANT,
            tool_calls=[
                ToolCall(
                    id=tool_call_id,
                    function={"name": func_name, "arguments": "{}"},
                )
            ],
            content=None,
            chat_model="elroy",
        ),
        ContextMessage(
            role=TOOL,
            tool_call_id=tool_call_id,
            content=func_response.model_dump_json() if isinstance(func_response, BaseModel) else func_response,
            chat_model="elroy",
        ),
    ]


@tool
def add_memory_to_current_context(ctx: ElroyContext, memory_name: str) -> str:
    """Adds memory with the given name to the current conversation context.

    Args:
        memory_name (str): The name of the memory to add to context

    Returns:
        str: Status message indicating success or failure of adding memory
    """
    from ..recall.operations import add_to_current_context_by_name

    return add_to_current_context_by_name(ctx, memory_name, Memory)


@tool
def drop_memory_from_current_context(ctx: ElroyContext, memory_name: str) -> str:
    """Drops the memory with the given name from current context. Does NOT delete the memory.

    Args:
        memory_name (str): Name of the memory to remove from context

    Returns:
        str: Status message indicating success or failure of removing memory
    """
    from ..recall.operations import drop_from_context_by_name

    return drop_from_context_by_name(ctx, memory_name, Memory)
