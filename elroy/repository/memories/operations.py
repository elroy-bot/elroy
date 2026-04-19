from collections.abc import Iterable

from ...core.async_tasks import schedule_task
from ...core.ctx import ElroyContext
from ...core.logging import log_execution_time
from ...db.db_models import EmbeddableSqlModel, Memory, MemoryOperationTracker, MemorySource
from ..context_messages.data_models import ContextMessage
from ..context_messages.queries import ContextMessageReadStore
from ..recall.factory import build_recall_context_bridge, build_recall_indexer
from ..user.queries import do_get_user_preferred_name, get_assistant_name
from .consolidation import consolidate_memories
from .memory_lifecycle_orchestrator import (
    MemoryLifecycleConfig,
    MemoryLifecycleDependencies,
    MemoryLifecycleOrchestrator,
)
from .store import MemoryStore, MemoryStoreConfig
from .summarizer import MemorySummarizer, MemorySummarizerMetadataProviders


def _store(ctx: ElroyContext) -> MemoryStore:
    return MemoryStore(
        db=ctx.db,
        user_id=ctx.user_id,
        config=MemoryStoreConfig(memory_dir_path=ctx.memory_dir_path),
    )


def _summarizer(ctx: ElroyContext) -> MemorySummarizer:
    return MemorySummarizer(
        fast_llm=ctx.fast_llm,
        metadata_providers=MemorySummarizerMetadataProviders(
            get_user_preferred_name_fn=lambda: do_get_user_preferred_name(ctx.db.session, ctx.user_id),
            get_assistant_name_fn=lambda: get_assistant_name(ctx),
        ),
    )


def _orchestrator(ctx: ElroyContext) -> MemoryLifecycleOrchestrator:
    context_message_read_store = ContextMessageReadStore(ctx.db, ctx.user_id)
    recall_context_bridge = build_recall_context_bridge(ctx)
    recall_indexer = build_recall_indexer(ctx)

    return MemoryLifecycleOrchestrator(
        store=_store(ctx),
        summarizer=_summarizer(ctx),
        config=MemoryLifecycleConfig(
            memories_between_consolidation=ctx.memories_between_consolidation,
        ),
        dependencies=MemoryLifecycleDependencies(
            get_context_messages_fn=lambda: list(context_message_read_store.get_context_messages()),
            schedule_consolidation_fn=lambda: schedule_task(consolidate_memories, ctx),
            remove_from_context_fn=recall_context_bridge.remove_from_context,
            add_to_context_fn=recall_context_bridge.add_to_context,
            upsert_embedding_if_needed_fn=recall_indexer.upsert_embedding_if_needed,
        ),
    )


def get_or_create_memory_op_tracker(ctx: ElroyContext) -> MemoryOperationTracker:
    return _store(ctx).get_or_create_memory_op_tracker()


@log_execution_time
def create_mem_from_current_context(ctx: ElroyContext):
    _orchestrator(ctx).create_mem_from_current_context()


def manually_record_user_memory(ctx: ElroyContext, text: str, name: str | None = None) -> None:
    """Manually record a memory for the user."""
    _orchestrator(ctx).manually_record_user_memory(text, name)


def formulate_memory(ctx: ElroyContext, context_messages: list[ContextMessage]) -> tuple[str, str]:
    return _summarizer(ctx).formulate_memory(context_messages)


def mark_inactive(ctx: ElroyContext, item: EmbeddableSqlModel):
    _orchestrator(ctx).mark_inactive(item)


def do_create_memory_from_ctx_msgs(ctx: ElroyContext, name: str, text: str) -> Memory:
    """Creates a memory with the current context message set designated as source."""
    return _orchestrator(ctx).do_create_memory_from_ctx_msgs(name, text)


def do_create_memory(
    ctx: ElroyContext,
    name: str,
    text: str,
    source_metadata: Iterable[MemorySource],
    add_mem_to_context: bool,
) -> Memory:
    return _orchestrator(ctx).do_create_memory(name, text, source_metadata, add_mem_to_context)


def do_create_op_tracked_memory(
    ctx: ElroyContext,
    name: str,
    text: str,
    source_metadata: Iterable[MemorySource],
    add_mem_to_context: bool,
) -> Memory:
    return _orchestrator(ctx).do_create_op_tracked_memory(name, text, source_metadata, add_mem_to_context)
