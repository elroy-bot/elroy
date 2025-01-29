import json
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlmodel import select

from ...config.constants import MAX_MEMORY_LENGTH, tool
from ...config.ctx import ElroyContext
from ...config.llm import ChatModel
from ...db.db_models import EmbeddableSqlModel, Memory, MemoryOperationTracker
from ...llm.client import query_llm
from ...utils.utils import run_in_background_thread
from ..context_messages.data_models import ContextMessage
from .consolidation import consolidate_memories


def get_or_create_memory_op_tracker(ctx: ElroyContext) -> MemoryOperationTracker:
    tracker = ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == ctx.user_id)).one_or_none()

    if tracker:
        return tracker
    else:
        # Create a new tracker for the user if it doesn't exist
        tracker = MemoryOperationTracker(user_id=ctx.user_id, memories_since_consolidation=0)
        return tracker


def memory_consolidation_check(func) -> Callable[..., Any]:
    @wraps(func)  # Add this line
    def wrapper(ctx: ElroyContext, *args, **kwargs):
        result = func(ctx, *args, **kwargs)

        logging.info("Checking memory consolidation")

        tracker = get_or_create_memory_op_tracker(ctx)

        tracker.memories_since_consolidation += 1
        logging.info(f"{tracker.memories_since_consolidation} memories since last consolidation")

        if tracker.memories_since_consolidation >= ctx.memories_between_consolidation:
            # Run consolidate_memories in a background thread
            logging.info("Running memory consolidation")
            run_in_background_thread(consolidate_memories, ctx)
            logging.info("Memory consolidation started in background thread")
            tracker.memories_since_consolidation = 0
        else:
            logging.info("Not running memory consolidation")
        ctx.db.add(tracker)
        ctx.db.commit()
        return result

    return wrapper


@memory_consolidation_check
@tool
def create_memory(ctx: ElroyContext, name: str, text: str) -> str:
    """Creates a new memory for the assistant.

    Examples of good and bad memory titles are below. Note that in the BETTER examples, some titles have been split into two:

    BAD:
    - [User Name]'s project progress and personal goals: 'Personal goals' is too vague, and the title describes two different topics.

    BETTER:
    - [User Name]'s project on building a treehouse: More specific, and describes a single topic.
    - [User Name]'s goal to be more thoughtful in conversation: Describes a specific goal.

    BAD:
    - [User Name]'s weekend plans: 'Weekend plans' is too vague, and dates must be referenced in ISO 8601 format.

    BETTER:
    - [User Name]'s plan to attend a concert on 2022-02-11: More specific, and includes a specific date.

    BAD:
    - [User Name]'s preferred name and well being: Two different topics, and 'well being' is too vague.

    BETTER:
    - [User Name]'s preferred name: Describes a specific topic.
    - [User Name]'s feeling of rejuvenation after rest: Describes a specific topic.

    Args:
        context (ElroyContext): _description_
        name (str): The name of the memory. Should be specific and discuss one topic.
        text (str): The text of the memory.

    Returns:
        str: Confirmation message that the memory was created.
    """
    do_create_memory(ctx, name, text)

    return f"New memory created: {name}"


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

    create_memory(ctx, name, text)


async def formulate_memory(
    chat_model: ChatModel, user_preferred_name: Optional[str], context_messages: List[ContextMessage]
) -> Tuple[str, str]:
    from ...llm.prompts import summarize_for_memory
    from ..context_messages.transform import format_context_messages

    return await summarize_for_memory(
        chat_model,
        format_context_messages(context_messages, user_preferred_name),
        user_preferred_name,
    )


def mark_inactive(ctx: ElroyContext, item: EmbeddableSqlModel):
    from ..embeddable import remove_from_context

    item.is_active = False
    ctx.db.add(item)
    ctx.db.commit()
    remove_from_context(ctx, item)


def do_create_memory(ctx: ElroyContext, name: str, text: str, source_metadata: List[Dict] = []) -> Memory:
    from ...repository.embeddings import upsert_embedding_if_needed
    from ..embeddable import add_to_context

    memory = Memory(
        user_id=ctx.user_id,
        name=name,
        text=text,
        source_metadata=json.dumps(source_metadata),
    )
    ctx.db.add(memory)
    ctx.db.commit()
    ctx.db.refresh(memory)

    upsert_embedding_if_needed(ctx, memory)
    add_to_context(ctx, memory)
    return memory
