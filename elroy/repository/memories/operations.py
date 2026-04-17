from collections.abc import Iterable

from ...core.async_tasks import schedule_task
from ...core.ctx import ElroyContext
from ...core.logging import log_execution_time
from ...db.db_models import EmbeddableSqlModel, Memory, MemoryOperationTracker, MemorySource
from ..context_messages.data_models import ContextMessage
from ..context_messages.queries import ContextMessageQueryService
from ..user.queries import do_get_user_preferred_name, get_assistant_name
from .consolidation import consolidate_memories
from .memory_lifecycle_orchestrator import (
    MemoryLifecycleCallbacks,
    MemoryLifecycleConfig,
    MemoryLifecycleMetadataProviders,
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
    context_message_query_service = ContextMessageQueryService(ctx.db, ctx.user_id)

    def remove_from_context(item: EmbeddableSqlModel) -> None:
        from ..recall.operations import remove_from_context as _remove_from_context

        _remove_from_context(ctx, item)

    def add_to_context(memory: Memory) -> None:
        from ..recall.operations import add_to_context as _add_to_context

        _add_to_context(ctx, memory)

    def upsert_embedding_if_needed(item: EmbeddableSqlModel) -> None:
        from ..recall.operations import upsert_embedding_if_needed as _upsert_embedding_if_needed

        _upsert_embedding_if_needed(ctx, item)

    return MemoryLifecycleOrchestrator(
        store=_store(ctx),
        summarizer=_summarizer(ctx),
        config=MemoryLifecycleConfig(
            memories_between_consolidation=ctx.memories_between_consolidation,
        ),
        metadata_providers=MemoryLifecycleMetadataProviders(
            get_context_messages_fn=lambda: list(context_message_query_service.get_context_messages()),
        ),
        callbacks=MemoryLifecycleCallbacks(
            schedule_consolidation_fn=lambda: schedule_task(consolidate_memories, ctx),
            remove_from_context_fn=remove_from_context,
            add_to_context_fn=add_to_context,
            upsert_embedding_if_needed_fn=upsert_embedding_if_needed,
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
