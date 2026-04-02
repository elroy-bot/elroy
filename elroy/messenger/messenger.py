from collections.abc import Iterator

from pydantic import BaseModel

from ..core.ctx import ElroyContext
from ..core.services.conversation_service import ConversationService
from ..core.tracing import tracer


@tracer.chain
def process_message(
    *,
    role: str,
    ctx: ElroyContext,
    msg: str,
    enable_tools: bool = True,
    force_tool: str | None = None,
) -> Iterator[BaseModel]:
    yield from ConversationService(ctx).process_message(
        role=role,
        msg=msg,
        enable_tools=enable_tools,
        force_tool=force_tool,
    )
