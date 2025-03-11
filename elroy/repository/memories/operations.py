import json
import logging
from threading import Thread
from typing import Iterable, List, Optional, Tuple

from sqlmodel import select

from ... import tracer_provider
from ...config.constants import MAX_MEMORY_LENGTH, SYSTEM, user_only_tool
from ...config.ctx import ElroyContext
from ...config.llm import ChatModel
from ...db.db_models import (
    EmbeddableSqlModel,
    Memory,
    MemoryOperationTracker,
    MemorySource,
)
from ...llm.client import query_llm
from ...utils.utils import run_in_background
from ..context_messages.data_models import ContextMessage
from ..context_messages.queries import get_or_create_context_message_set
from .consolidation import consolidate_memories

tracer = tracer_provider.get_tracer(__name__)


def get_or_create_memory_op_tracker(ctx: ElroyContext) -> MemoryOperationTracker:
    tracker = ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == ctx.user_id)).one_or_none()

    if tracker:
        return tracker
    else:
        # Create a new tracker for the user if it doesn't exist
        tracker = MemoryOperationTracker(user_id=ctx.user_id, memories_since_consolidation=0)
        return tracker


@tracer.chain
def do_memory_consolidation_check(ctx: ElroyContext) -> Optional[Thread]:
    logging.info("Checking memory consolidation")

    tracker = get_or_create_memory_op_tracker(ctx)

    tracker.memories_since_consolidation += 1
    logging.info(f"{tracker.memories_since_consolidation} memories since last consolidation")
    thread = None

    if tracker.memories_since_consolidation >= ctx.memories_between_consolidation:
        # Run consolidate_memories in a background thread.
        # Note: this will reset the tracker, whether or not the background task completes.
        # This prevents infinite retries if consolidation is failing, but it might be better to fail fast here
        logging.info("Running memory consolidation")
        thread = run_in_background(consolidate_memories, ctx)
        tracker.memories_since_consolidation = 0
    else:
        logging.info("Not running memory consolidation")
    ctx.db.add(tracker)
    ctx.db.commit()
    return thread


@user_only_tool
def remember_convo(ctx: ElroyContext):
    """Creates a memory of the current conversation, and refreshes the context. Good for topic changes."""
    from ...messenger import process_message
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


def formulate_memory(
    chat_model: ChatModel, user_preferred_name: str, assistant_name: str, context_messages: List[ContextMessage]
) -> Tuple[str, str]:
    from ...llm.prompts import summarize_for_memory
    from ..context_messages.transforms import format_context_messages

    return summarize_for_memory(
        chat_model,
        format_context_messages(
            context_messages,
            user_preferred_name,
            assistant_name,
        ),
        user_preferred_name,
    )


def mark_inactive(ctx: ElroyContext, item: EmbeddableSqlModel):
    from ..recall.operations import remove_from_context

    item.is_active = False
    ctx.db.add(item)
    ctx.db.commit()
    remove_from_context(ctx, item)


def do_create_memory_from_ctx_msgs(ctx: ElroyContext, name: str, text: str) -> Tuple[Memory, Optional[Thread]]:
    """Creates a memory with the current context message set designated as source."""

    return do_create_memory(
        ctx,
        name,
        text,
        [get_or_create_context_message_set(ctx)],
        True,
        True,
    )


@tracer.chain
def do_create_memory(
    ctx: ElroyContext,
    name: str,
    text: str,
    source_metadata: Iterable[MemorySource],
    check_consolidation: bool,
    add_mem_to_context: bool,
) -> Tuple[Memory, Optional[Thread]]:
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

    if check_consolidation:
        return (memory, do_memory_consolidation_check(ctx))
    else:
        return (memory, None)
