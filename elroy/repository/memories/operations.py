import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import select

from ...core.async_tasks import schedule_task
from ...core.constants import MAX_MEMORY_LENGTH
from ...core.ctx import ElroyContext
from ...core.logging import get_logger, log_execution_time
from ...db.db_models import (
    EmbeddableSqlModel,
    Memory,
    MemoryOperationTracker,
    MemorySource,
)
from ...db.db_session import DbSession
from ...llm.client import LlmClient
from ..context_messages.data_models import ContextMessage
from ..context_messages.queries import ContextMessageQueryService, get_or_create_context_message_set
from ..user.queries import do_get_user_preferred_name, get_assistant_name
from .consolidation import consolidate_memories

logger = get_logger()


@dataclass(frozen=True)
class MemoryOperationConfig:
    memory_dir_path: Path
    memories_between_consolidation: int


@dataclass(frozen=True)
class MemoryOperationMetadataProviders:
    get_context_messages_fn: Callable[[], list[ContextMessage]]
    get_user_preferred_name_fn: Callable[[], str | None]
    get_assistant_name_fn: Callable[[], str]


@dataclass(frozen=True)
class MemoryOperationCallbacks:
    schedule_consolidation_fn: Callable[[], None]
    remove_from_context_fn: Callable[[EmbeddableSqlModel], None]
    add_to_context_fn: Callable[[Memory], None]
    upsert_embedding_if_needed_fn: Callable[[EmbeddableSqlModel], None]


class MemoryOperationService:
    def __init__(
        self,
        db: DbSession,
        user_id: int,
        fast_llm: LlmClient,
        config: MemoryOperationConfig,
        metadata_providers: MemoryOperationMetadataProviders,
        callbacks: MemoryOperationCallbacks,
    ):
        self.db = db
        self.user_id = user_id
        self.fast_llm = fast_llm
        self.config = config
        self.metadata_providers = metadata_providers
        self.callbacks = callbacks

    def get_or_create_memory_op_tracker(self) -> MemoryOperationTracker:
        tracker = self.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == self.user_id)).one_or_none()

        if tracker:
            return tracker
        return MemoryOperationTracker(user_id=self.user_id, memories_since_consolidation=0)

    @log_execution_time
    def create_mem_from_current_context(self) -> None:
        logger.info("Creating memory from current context")
        memory_title, memory_text = self.formulate_memory(self.metadata_providers.get_context_messages_fn())
        self.do_create_memory_from_ctx_msgs(memory_title, memory_text)

    def manually_record_user_memory(self, text: str, name: str | None = None) -> None:
        if not text:
            raise ValueError("Memory text cannot be empty.")

        if len(text) > MAX_MEMORY_LENGTH:
            raise ValueError(f"Memory text exceeds maximum length of {MAX_MEMORY_LENGTH} characters.")

        if not name:
            name = self.fast_llm.query_llm(
                system="Given text representing a memory, your task is to come up with a short title for a memory. "
                "If the title mentions dates, it should be specific dates rather than relative ones.",
                prompt=text,
            )

        self.do_create_memory(name, text, [], True)

    def formulate_memory(self, context_messages: list[ContextMessage]) -> tuple[str, str]:
        from ...llm.prompts import summarize_for_memory
        from ..context_messages.transforms import format_context_messages

        user_preferred_name = self.metadata_providers.get_user_preferred_name_fn() or "User"

        return summarize_for_memory(
            self.fast_llm,
            format_context_messages(
                context_messages,
                user_preferred_name,
                self.metadata_providers.get_assistant_name_fn(),
            ),
            user_preferred_name,
        )

    def mark_inactive(self, item: EmbeddableSqlModel) -> None:
        if isinstance(item, Memory) and item.file_path:
            from ..memories.file_storage import archive_memory_file

            file_path = Path(item.file_path)
            if file_path.exists():
                dest = archive_memory_file(file_path, self.config.memory_dir_path / "archive")
                item.file_path = str(dest)

        item.is_active = False
        self.db.add(item)
        self.db.commit()
        self.db.update_embedding_active(item)
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
        from ..memories.file_storage import write_memory_file

        memory = self.db.persist(
            Memory(
                user_id=self.user_id,
                name=name,
                source_metadata=json.dumps([x.to_memory_source_d() for x in source_metadata]),
            )
        )

        assert memory.id is not None
        existing_paths: set[str] = {str(p) for p in self.config.memory_dir_path.glob("*.md")}
        file_path = write_memory_file(self.config.memory_dir_path, memory, text, existing_paths)
        memory.file_path = str(file_path)
        self.db.add(memory)
        self.db.commit()

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

        tracker = self.get_or_create_memory_op_tracker()

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


def _service(ctx: ElroyContext) -> MemoryOperationService:
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

    return MemoryOperationService(
        db=ctx.db,
        user_id=ctx.user_id,
        fast_llm=ctx.fast_llm,
        config=MemoryOperationConfig(
            memory_dir_path=ctx.memory_dir_path,
            memories_between_consolidation=ctx.memories_between_consolidation,
        ),
        metadata_providers=MemoryOperationMetadataProviders(
            get_context_messages_fn=lambda: list(context_message_query_service.get_context_messages()),
            get_user_preferred_name_fn=lambda: do_get_user_preferred_name(ctx.db.session, ctx.user_id),
            get_assistant_name_fn=lambda: get_assistant_name(ctx),
        ),
        callbacks=MemoryOperationCallbacks(
            schedule_consolidation_fn=lambda: schedule_task(consolidate_memories, ctx),
            remove_from_context_fn=remove_from_context,
            add_to_context_fn=add_to_context,
            upsert_embedding_if_needed_fn=upsert_embedding_if_needed,
        ),
    )


def get_or_create_memory_op_tracker(ctx: ElroyContext) -> MemoryOperationTracker:
    return _service(ctx).get_or_create_memory_op_tracker()


@log_execution_time
def create_mem_from_current_context(ctx: ElroyContext):
    _service(ctx).create_mem_from_current_context()


def manually_record_user_memory(ctx: ElroyContext, text: str, name: str | None = None) -> None:
    """Manually record a memory for the user."""
    _service(ctx).manually_record_user_memory(text, name)


def formulate_memory(ctx: ElroyContext, context_messages: list[ContextMessage]) -> tuple[str, str]:
    return _service(ctx).formulate_memory(context_messages)


def mark_inactive(ctx: ElroyContext, item: EmbeddableSqlModel):
    _service(ctx).mark_inactive(item)


def do_create_memory_from_ctx_msgs(ctx: ElroyContext, name: str, text: str) -> Memory:
    """Creates a memory with the current context message set designated as source."""
    return _service(ctx).do_create_memory_from_ctx_msgs(name, text)


def do_create_memory(
    ctx: ElroyContext,
    name: str,
    text: str,
    source_metadata: Iterable[MemorySource],
    add_mem_to_context: bool,
) -> Memory:
    return _service(ctx).do_create_memory(name, text, source_metadata, add_mem_to_context)


def do_create_op_tracked_memory(
    ctx: ElroyContext,
    name: str,
    text: str,
    source_metadata: Iterable[MemorySource],
    add_mem_to_context: bool,
) -> Memory:
    return _service(ctx).do_create_op_tracked_memory(name, text, source_metadata, add_mem_to_context)
