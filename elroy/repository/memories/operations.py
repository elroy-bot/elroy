import json
import logging
from functools import partial
from typing import Dict, List, Optional, Sequence, Tuple

from sqlmodel import select
from toolz import pipe
from toolz.curried import map

from ...config.config import ChatModel
from ...config.ctx import ElroyContext
from ...db.db_models import EmbeddableSqlModel, Memory
from ...llm.client import query_llm
from ..data_models import ContextMessage
from .consolidation import memory_consolidation_check


def get_active_memories(ctx: ElroyContext) -> List[Memory]:
    """Fetch all active memories for the user"""
    return list(
        ctx.db.exec(
            select(Memory).where(
                Memory.user_id == ctx.user_id,
                Memory.is_active == True,
            )
        ).all()
    )


def create_consolidated_memory(ctx: ElroyContext, name: str, text: str, sources: Sequence[EmbeddableSqlModel]):
    pass

    logging.info(f"Creating consolidated memory {name} for user {ctx.user_id}")

    memory = pipe(
        sources,
        map(lambda x: {"source_id": x.id, "source_type": x.__class__.__name__}),
        list,
        partial(_do_create_memory, ctx, name, text),
        # Do NOT add this memory to context, it's not necessarrily relevant to the conversation
    )

    [mark_inactive(ctx, m) for m in sources]
    assert isinstance(memory, Memory)
    memory_id = memory.id
    assert memory_id
    return memory_id


@memory_consolidation_check
def create_memory(ctx: ElroyContext, name: str, text: str) -> str:
    """Creates a new memory for the assistant.

    Examples of good and bad memory titles are below. Note, the BETTER examples, some titles have been split into two.:

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
        int: The database ID of the memory.
    """
    _do_create_memory(ctx, name, text)

    return f"New memory created: {name}"


def _do_create_memory(ctx: ElroyContext, name: str, text: str, source_metadata: List[Dict] = []) -> Memory:
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


MAX_MEMORY_LENGTH = 12000  # Characters


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
    from ...messaging.context import format_context_messages

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
