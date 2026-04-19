from ...core.ctx import ElroyContext
from ...db.db_models import EmbeddableSqlModel
from .context_bridge import RecallContextBridge
from .indexer import RecallIndexer


def _indexer(ctx: ElroyContext) -> RecallIndexer:
    return RecallIndexer(
        db=ctx.db,
        user_id=ctx.user_id,
        llm=ctx.llm,
    )


def _context_bridge(ctx: ElroyContext) -> RecallContextBridge:
    from ..context_messages.operations import add_context_messages, remove_context_messages
    from ..context_messages.queries import get_context_messages

    return RecallContextBridge(
        db=ctx.db,
        user_id=ctx.user_id,
        get_context_messages_fn=lambda: get_context_messages(ctx),
        add_context_messages_fn=lambda messages: add_context_messages(ctx, messages),
        remove_context_messages_fn=lambda messages: remove_context_messages(ctx, messages),
    )


def upsert_embedding_if_needed(ctx: ElroyContext, row: EmbeddableSqlModel) -> None:
    _indexer(ctx).upsert_embedding_if_needed(row)


def add_to_context(ctx: ElroyContext, memory: EmbeddableSqlModel) -> None:
    _context_bridge(ctx).add_to_context(memory)


def remove_from_context(ctx: ElroyContext, memory: EmbeddableSqlModel):
    _context_bridge(ctx).remove_from_context(memory)


def add_to_current_context_by_name(ctx: ElroyContext, name: str, memory_type: type[EmbeddableSqlModel]) -> str:
    return _context_bridge(ctx).add_to_current_context_by_name(name, memory_type)


def drop_from_context_by_name(ctx: ElroyContext, name: str, memory_type: type[EmbeddableSqlModel]) -> str:
    return _context_bridge(ctx).drop_from_context_by_name(name, memory_type)
