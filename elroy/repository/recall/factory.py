from ...core.ctx import ElroyContext
from ..context_messages.factory import build_context_message_read_store, build_context_refresh_orchestrator
from .context_bridge import RecallContextBridge
from .indexer import RecallIndexer


def build_recall_indexer(ctx: ElroyContext) -> RecallIndexer:
    return RecallIndexer(
        db=ctx.db,
        user_id=ctx.user_id,
        llm=ctx.llm,
    )


def build_recall_context_bridge(ctx: ElroyContext) -> RecallContextBridge:
    context_refresh_orchestrator = build_context_refresh_orchestrator(ctx)
    context_message_read_store = build_context_message_read_store(ctx)
    return RecallContextBridge(
        db=ctx.db,
        user_id=ctx.user_id,
        get_context_messages_fn=context_message_read_store.get_context_messages,
        add_context_messages_fn=context_refresh_orchestrator.add_context_messages,
        remove_context_messages_fn=context_refresh_orchestrator.store.remove_context_messages,
    )
