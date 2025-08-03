import json
from functools import partial
from typing import Iterable, List, Optional, Tuple

from sqlmodel import select
from toolz import concat, juxt, pipe
from toolz.curried import filter

from ...core.async_tasks import schedule_task
from ...core.constants import MAX_MEMORY_LENGTH, SYSTEM, user_only_tool
from ...core.ctx import ElroyContext
from ...core.logging import get_logger, log_execution_time
from ...core.tracing import tracer
from ...db.db_models import (
    EmbeddableSqlModel,
    Memory,
    MemoryOperationTracker,
    MemorySource,
)
from ...llm.client import get_embedding, query_llm, query_llm_with_response_format
from ..context_messages.data_models import ContextMessage
from ..context_messages.queries import (
    get_context_messages,
    get_or_create_context_message_set,
)
from ..recall.queries import (
    get_most_relevant_goals,
    get_most_relevant_memories,
    get_most_relevant_reminders,
)
from ..user.queries import do_get_user_preferred_name, get_assistant_name
from .consolidation import consolidate_memories
from .models import MemoryResponse
from .queries import filter_for_relevance

logger = get_logger()


def get_or_create_memory_op_tracker(ctx: ElroyContext) -> MemoryOperationTracker:
    tracker = ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == ctx.user_id)).one_or_none()

    if tracker:
        return tracker
    else:
        # Create a new tracker for the user if it doesn't exist
        tracker = MemoryOperationTracker(user_id=ctx.user_id, memories_since_consolidation=0)
        return tracker


def augment_memory(ctx: ElroyContext, content: str) -> MemoryResponse:
    memories: List[EmbeddableSqlModel] = pipe(
        content,
        partial(get_embedding, ctx.embedding_model),
        lambda x: juxt(get_most_relevant_goals, get_most_relevant_memories, get_most_relevant_reminders)(ctx, x),
        concat,
        list,
        filter(lambda x: x is not None),
        list,
        lambda mems: filter_for_relevance(
            ctx.chat_model,
            content,
            mems,
            lambda m: m.to_fact(),
        ),
        list,
    )

    if len(memories) > 0:
        mem_str = "\n".join([m.to_fact() for m in memories])
        return query_llm_with_response_format(
            ctx.chat_model,
            system="""
            Your job is to augment text representing a memory. You will be provided with the initial text, as well as memories from storage which have been deemed to be relevant. Use this information to augment the text with enough context such that future readers can better understand the memory.

            This could include information about how subjects relate to the user.

            If there is still unknown information, simply omit that context, do not add any content about how you don't know.

            Respond with both augmented text, and a short title for the memory.
            """,
            prompt=f"""
            # Original Text

            {content}

            # Relevant memories

            {mem_str}
            """,
            response_format=MemoryResponse,
        )

    else:
        return MemoryResponse(title=content[:25], text=content)


@log_execution_time
def create_mem_from_current_context(ctx: ElroyContext):
    memory_title, memory_text = formulate_memory(
        ctx,
        list(get_context_messages(ctx)),
    )
    do_create_memory_from_ctx_msgs(ctx, memory_title, memory_text)


@user_only_tool
def remember_convo(ctx: ElroyContext):
    """Creates a memory of the current conversation, and refreshes the context. Good for topic changes."""
    from ...messenger.messenger import process_message
    from .tools import create_memory

    yield from process_message(
        role=SYSTEM,
        ctx=ctx,
        msg="The use has triggered a remember_convo command. Through goals in context or via a new memory, capture information about the current converstaion",
        force_tool=create_memory.__name__,
        enable_tools=True,
    )


def manually_record_user_memory(ctx: ElroyContext, text: str, name: Optional[str] = None) -> None:
    """Manually record a memory for the user.

    Args:
        context (ElroyContext): The context of the user.
        name (str): The name of the memory. Should be specific and discuss one topic.
        text (str): The text of the memory.
    """

    if not text:
        raise ValueError("Memory text cannot be empty.")

    if len(text) > MAX_MEMORY_LENGTH:
        raise ValueError(f"Memory text exceeds maximum length of {MAX_MEMORY_LENGTH} characters.")

    if not name:
        name = query_llm(
            ctx.chat_model,
            system="Given text representing a memory, your task is to come up with a short title for a memory. "
            "If the title mentions dates, it should be specific dates rather than relative ones.",
            prompt=text,
        )

    do_create_memory_from_ctx_msgs(ctx, name, text)


def formulate_memory(ctx: ElroyContext, context_messages: List[ContextMessage]) -> Tuple[str, str]:
    from ...llm.prompts import summarize_for_memory
    from ..context_messages.transforms import format_context_messages

    user_preferred_name = do_get_user_preferred_name(ctx.db.session, ctx.user_id)

    return summarize_for_memory(
        ctx.chat_model,
        format_context_messages(
            context_messages,
            user_preferred_name,
            get_assistant_name(ctx),
        ),
        user_preferred_name,
    )


def mark_inactive(ctx: ElroyContext, item: EmbeddableSqlModel):
    from ..recall.operations import remove_from_context

    item.is_active = False
    ctx.db.add(item)
    ctx.db.commit()
    remove_from_context(ctx, item)


def do_create_memory_from_ctx_msgs(ctx: ElroyContext, name: str, text: str) -> Memory:
    """Creates a memory with the current context message set designated as source."""

    return do_create_op_tracked_memory(
        ctx,
        name,
        text,
        [get_or_create_context_message_set(ctx)],
        get_or_create_memory_op_tracker(ctx),
        True,
    )


@tracer.chain
def do_create_memory(
    ctx: ElroyContext,
    name: str,
    text: str,
    source_metadata: Iterable[MemorySource],
    add_mem_to_context: bool,
) -> Memory:
    from ..recall.operations import add_to_context, upsert_embedding_if_needed

    memory = Memory(
        user_id=ctx.user_id,
        name=name,
        text=text,
        source_metadata=json.dumps(
            [x.to_memory_source_d() for x in source_metadata],
        ),
    )

    ctx.db.add(memory)
    ctx.db.commit()
    ctx.db.refresh(memory)
    upsert_embedding_if_needed(ctx, memory)
    if add_mem_to_context:
        add_to_context(ctx, memory)
    return memory


def do_create_op_tracked_memory(
    ctx: ElroyContext,
    name: str,
    text: str,
    source_metadata: Iterable[MemorySource],
    tracker: MemoryOperationTracker,
    add_mem_to_context: bool,
) -> Memory:

    memory = do_create_memory(ctx, name, text, source_metadata, add_mem_to_context)

    logger.info("Checking memory consolidation")
    tracker.messages_since_memory = 0
    tracker.memories_since_consolidation += 1
    logger.info(f"{tracker.memories_since_consolidation} memories since last consolidation")

    if tracker.memories_since_consolidation >= ctx.memories_between_consolidation:
        # Run consolidate_memories in a background thread.
        # Note: this will reset the tracker, whether or not the background task completes.
        # This prevents infinite retries if consolidation is failing, but it might be better to fail fast here
        logger.info("Running memory consolidation")
        schedule_task(consolidate_memories, ctx)
        tracker.memories_since_consolidation = 0
    else:
        logger.info("Not running memory consolidation")
    ctx.db.add(tracker)
    ctx.db.commit()
    return memory
