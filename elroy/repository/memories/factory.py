from ...core.async_tasks import schedule_task
from ...core.turn import TurnContext
from ...db.db_models import MemoryOperationTracker
from ..context_messages.data_models import ContextMessage
from ..context_messages.factory import build_context_message_read_store
from ..context_messages.session import build_context_message_session
from ..recall.factory import build_recall_context_bridge, build_recall_indexer
from ..user.queries import do_get_user_preferred_name, get_assistant_name
from ..user.session import build_user_runtime, build_user_session
from .consolidation import do_consolidate_memories
from .memory_lifecycle_orchestrator import (
    MemoryLifecycleConfig,
    MemoryLifecycleDependencies,
    MemoryLifecycleOrchestrator,
)
from .memory_recall_builder import MemoryRecallBuilder
from .memory_recall_orchestrator import MemoryRecallOrchestrator
from .queries import MemoryReadStore
from .runtime import build_memory_runtime
from .store import MemoryStore, MemoryStoreConfig
from .summarizer import MemorySummarizer, MemorySummarizerMetadataProviders


def build_memory_store(turn: TurnContext) -> MemoryStore:
    user_session = build_user_session(turn)
    runtime = build_memory_runtime(turn)
    return MemoryStore(
        db=user_session.db,
        user_id=user_session.user_id,
        config=MemoryStoreConfig(memory_dir_path=runtime.memory_dir_path),
    )


def build_memory_read_store(turn: TurnContext) -> MemoryReadStore:
    user_session = build_user_session(turn)
    return MemoryReadStore(user_session.db, user_session.user_id)


def build_memory_summarizer(turn: TurnContext) -> MemorySummarizer:
    user_session = build_user_session(turn)
    user_runtime = build_user_runtime(turn)
    runtime = build_memory_runtime(turn)
    return MemorySummarizer(
        fast_llm=runtime.fast_llm,
        metadata_providers=MemorySummarizerMetadataProviders(
            get_user_preferred_name_fn=lambda: do_get_user_preferred_name(user_session.db.session, user_session.user_id),
            get_assistant_name_fn=lambda: get_assistant_name(user_session, user_runtime),
        ),
    )


def build_memory_recall_builder() -> MemoryRecallBuilder:
    return MemoryRecallBuilder()


def build_memory_recall_orchestrator(turn: TurnContext) -> MemoryRecallOrchestrator:
    user_session = build_user_session(turn)
    runtime = build_memory_runtime(turn)
    return MemoryRecallOrchestrator(
        db=user_session.db,
        user_id=user_session.user_id,
        memory_config=runtime.memory_config,
        llm=runtime.llm,
        reflect=runtime.reflect,
        recall_builder=build_memory_recall_builder(),
    )


def build_memory_lifecycle_orchestrator(turn: TurnContext) -> MemoryLifecycleOrchestrator:
    recall_context_bridge = build_recall_context_bridge(turn)
    recall_indexer = build_recall_indexer(turn)
    context_message_read_store = build_context_message_read_store(build_context_message_session(turn))
    runtime = build_memory_runtime(turn)
    return MemoryLifecycleOrchestrator(
        store=build_memory_store(turn),
        summarizer=build_memory_summarizer(turn),
        config=MemoryLifecycleConfig(
            memories_between_consolidation=runtime.memories_between_consolidation,
        ),
        dependencies=MemoryLifecycleDependencies(
            get_context_messages_fn=lambda: list(context_message_read_store.get_context_messages()),
            schedule_consolidation_fn=lambda: schedule_task(do_consolidate_memories, turn),
            remove_from_context_fn=recall_context_bridge.remove_from_context,
            add_to_context_fn=recall_context_bridge.add_to_context,
            upsert_embedding_if_needed_fn=recall_indexer.upsert_embedding_if_needed,
        ),
    )


def get_or_create_memory_op_tracker(turn: TurnContext) -> MemoryOperationTracker:
    return build_memory_store(turn).get_or_create_memory_op_tracker()


def create_mem_from_current_context(turn: TurnContext) -> None:
    build_memory_lifecycle_orchestrator(turn).create_mem_from_current_context()


def formulate_memory(turn: TurnContext, context_messages: list[ContextMessage]) -> tuple[str, str]:
    return build_memory_summarizer(turn).formulate_memory(context_messages)
