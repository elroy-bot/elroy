from ...core.async_tasks import schedule_task
from ...core.ctx import ElroyContext
from ...db.db_models import MemoryOperationTracker
from ..context_messages.data_models import ContextMessage
from ..context_messages.factory import build_context_message_read_store
from ..recall.factory import build_recall_context_bridge, build_recall_indexer
from ..user.queries import do_get_user_preferred_name, get_assistant_name
from .consolidation import consolidate_memories
from .memory_lifecycle_orchestrator import (
    MemoryLifecycleConfig,
    MemoryLifecycleDependencies,
    MemoryLifecycleOrchestrator,
)
from .memory_recall_builder import MemoryRecallBuilder
from .memory_recall_orchestrator import MemoryRecallOrchestrator
from .queries import MemoryReadStore
from .store import MemoryStore, MemoryStoreConfig
from .summarizer import MemorySummarizer, MemorySummarizerMetadataProviders


def build_memory_store(ctx: ElroyContext) -> MemoryStore:
    return MemoryStore(
        db=ctx.db,
        user_id=ctx.user_id,
        config=MemoryStoreConfig(memory_dir_path=ctx.memory_dir_path),
    )


def build_memory_read_store(ctx: ElroyContext) -> MemoryReadStore:
    return MemoryReadStore(ctx.db, ctx.user_id)


def build_memory_summarizer(ctx: ElroyContext) -> MemorySummarizer:
    return MemorySummarizer(
        fast_llm=ctx.fast_llm,
        metadata_providers=MemorySummarizerMetadataProviders(
            get_user_preferred_name_fn=lambda: do_get_user_preferred_name(ctx.db.session, ctx.user_id),
            get_assistant_name_fn=lambda: get_assistant_name(ctx),
        ),
    )


def build_memory_recall_builder() -> MemoryRecallBuilder:
    return MemoryRecallBuilder()


def build_memory_recall_orchestrator(ctx: ElroyContext) -> MemoryRecallOrchestrator:
    return MemoryRecallOrchestrator(
        db=ctx.db,
        user_id=ctx.user_id,
        memory_config=ctx.memory_config,
        llm=ctx.llm,
        reflect=ctx.reflect,
        recall_builder=build_memory_recall_builder(),
    )


def build_memory_lifecycle_orchestrator(ctx: ElroyContext) -> MemoryLifecycleOrchestrator:
    recall_context_bridge = build_recall_context_bridge(ctx)
    recall_indexer = build_recall_indexer(ctx)
    context_message_read_store = build_context_message_read_store(ctx)
    return MemoryLifecycleOrchestrator(
        store=build_memory_store(ctx),
        summarizer=build_memory_summarizer(ctx),
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
    return build_memory_store(ctx).get_or_create_memory_op_tracker()


def create_mem_from_current_context(ctx: ElroyContext) -> None:
    build_memory_lifecycle_orchestrator(ctx).create_mem_from_current_context()


def formulate_memory(ctx: ElroyContext, context_messages: list[ContextMessage]) -> tuple[str, str]:
    return build_memory_summarizer(ctx).formulate_memory(context_messages)
