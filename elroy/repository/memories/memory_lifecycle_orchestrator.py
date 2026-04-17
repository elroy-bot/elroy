from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ...core.logging import get_logger, log_execution_time
from ...db.db_models import EmbeddableSqlModel, Memory, MemorySource
from ..context_messages.data_models import ContextMessage
from ..context_messages.queries import get_or_create_context_message_set
from .store import MemoryStore
from .summarizer import MemorySummarizer

logger = get_logger()


@dataclass(frozen=True)
class MemoryLifecycleConfig:
    memories_between_consolidation: int


@dataclass(frozen=True)
class MemoryLifecycleMetadataProviders:
    get_context_messages_fn: Callable[[], list[ContextMessage]]


@dataclass(frozen=True)
class MemoryLifecycleCallbacks:
    schedule_consolidation_fn: Callable[[], None]
    remove_from_context_fn: Callable[[EmbeddableSqlModel], None]
    add_to_context_fn: Callable[[Memory], None]
    upsert_embedding_if_needed_fn: Callable[[EmbeddableSqlModel], None]


class MemoryLifecycleOrchestrator:
    def __init__(
        self,
        store: MemoryStore,
        summarizer: MemorySummarizer,
        config: MemoryLifecycleConfig,
        metadata_providers: MemoryLifecycleMetadataProviders,
        callbacks: MemoryLifecycleCallbacks,
    ):
        self.store = store
        self.summarizer = summarizer
        self.config = config
        self.metadata_providers = metadata_providers
        self.callbacks = callbacks
        self.db = store.db
        self.user_id = store.user_id

    @log_execution_time
    def create_mem_from_current_context(self) -> None:
        logger.info("Creating memory from current context")
        memory_title, memory_text = self.summarizer.formulate_memory(self.metadata_providers.get_context_messages_fn())
        self.do_create_memory_from_ctx_msgs(memory_title, memory_text)

    def manually_record_user_memory(self, text: str, name: str | None = None) -> None:
        resolved_name = self.summarizer.ensure_memory_title(text, name)
        self.do_create_memory(resolved_name, text, [], True)

    def mark_inactive(self, item: EmbeddableSqlModel) -> None:
        self.store.mark_inactive(item)
        self.callbacks.remove_from_context_fn(item)

    def do_create_memory_from_ctx_msgs(self, name: str, text: str) -> Memory:
        return self.do_create_op_tracked_memory(
            name,
            text,
            [get_or_create_context_message_set(self.db, self.user_id)],
            True,
        )

    def do_create_memory(
        self,
        name: str,
        text: str,
        source_metadata: Iterable[MemorySource],
        add_mem_to_context: bool,
    ) -> Memory:
        memory = self.store.create_memory(name, text, source_metadata)
        self.callbacks.upsert_embedding_if_needed_fn(memory)
        if add_mem_to_context:
            self.callbacks.add_to_context_fn(memory)
        return memory

    def do_create_op_tracked_memory(
        self,
        name: str,
        text: str,
        source_metadata: Iterable[MemorySource],
        add_mem_to_context: bool,
    ) -> Memory:
        memory = self.do_create_memory(name, text, source_metadata, add_mem_to_context)

        tracker = self.store.get_or_create_memory_op_tracker()

        logger.info("Checking memory consolidation")
        tracker.messages_since_memory = 0
        tracker.memories_since_consolidation += 1
        tracker = self.db.persist(tracker)
        logger.info(f"{tracker.memories_since_consolidation} memories since last consolidation")

        if tracker.memories_since_consolidation >= self.config.memories_between_consolidation:
            logger.info("Running memory consolidation")
            self.callbacks.schedule_consolidation_fn()
            tracker.memories_since_consolidation = 0
            self.db.persist(tracker)
        else:
            logger.info("Not running memory consolidation")
        return memory
