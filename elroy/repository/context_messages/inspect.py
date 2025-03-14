from typing import List, Optional

from toolz import pipe
from toolz.curried import filter, map

from ...core.constants import ASSISTANT
from ...core.logging import get_logger
from ...utils.utils import last_or_none
from .data_models import ContextMessage

logger = get_logger()


def has_assistant_tool_call(
    tool_call_id: Optional[str],
    context_messages: List[ContextMessage],
) -> bool:
    """
    Assistant tool call message must be in the most recent assistant message
    """
    if not tool_call_id:
        logger.warning("Tool call ID is None")
        return False

    return pipe(
        context_messages,
        filter(lambda x: x.role == ASSISTANT),
        last_or_none,
        lambda msg: msg.tool_calls or [] if msg else [],
        map(lambda x: x.id),
        filter(lambda x: x == tool_call_id),
        any,
    )
