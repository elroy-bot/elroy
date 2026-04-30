from collections.abc import Iterator

from pydantic import BaseModel

from ..core.conversation_orchestrator import ConversationOrchestrator
from ..core.ctx import ElroyConfig
from ..core.session import open_turn_context
from ..core.turn import ElroySession


def process_message(
    *,
    role: str,
    ctx: ElroyConfig,
    session: ElroySession,
    msg: str,
    enable_tools: bool = True,
    force_tool: str | None = None,
) -> Iterator[BaseModel]:
    with open_turn_context(ctx, session) as turn:
        yield from ConversationOrchestrator(turn).process_message(
            role=role,
            msg=msg,
            enable_tools=enable_tools,
            force_tool=force_tool,
        )
