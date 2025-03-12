import json
from functools import partial
from typing import Iterable, List, Optional, Sequence, Union

from sqlmodel import select
from toolz import concat, juxt, pipe, unique
from toolz.curried import filter, map, remove, tail

from ... import tracer
from ...config.constants import SYSTEM
from ...config.ctx import ElroyContext
from ...db.db_models import (
    EmbeddableSqlModel,
    Goal,
    Memory,
    MemorySource,
    get_memory_source_class,
)
from ...llm.client import get_embedding, query_llm
from ..context_messages.data_models import ContextMessage, RecalledMemoryMetadata
from ..context_messages.transforms import (
    ContextMessageSetWithMessages,
    format_context_messages,
)
from ..recall.queries import (
    get_most_relevant_goal,
    get_most_relevant_memory,
    is_in_context,
)
from ..recall.transforms import to_recalled_memory_metadata
from ..user.queries import get_assistant_name
from ..user.tools import get_user_preferred_name




def db_get_memory_source_by_name(ctx: ElroyContext, source_type: str, name: str) -> Optional[MemorySource]:
    source_class = get_memory_source_class(source_type)

    if source_class == ContextMessageSetWithMessages:
        return ContextMessageSetWithMessages(ctx.db.session, int(name), ctx.user_id)
    elif hasattr(source_class, "name"):
        return ctx.db.exec(select(source_class).where(source_class.name == name, source_class.user_id == ctx.user_id)).first()  # type: ignore
    else:
        raise NotImplementedError(f"Cannot get source of type {source_type}")


def db_get_source_list_for_memory(ctx: ElroyContext, memory: Memory) -> Sequence[MemorySource]:
    if not memory.source_metadata:
        return []
    else:
        return pipe(
            memory.source_metadata,
            json.loads,
            map(lambda x: db_get_memory_source(ctx, x["source_type"], x["id"])),
            remove(lambda x: x is None),
            list,
        )  # type: ignore


def db_get_memory_source(ctx: ElroyContext, source_type: str, id: int) -> Optional[MemorySource]:
    source_class = get_memory_source_class(source_type)

    if source_class == ContextMessageSetWithMessages:
        return ContextMessageSetWithMessages(ctx.db.session, id, ctx.user_id)
    else:
        return ctx.db.exec(select(source_class).where(source_class.id == id, source_class.user_id == ctx.user_id)).first()


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


@tracer.chain
def get_relevant_memories(ctx: ElroyContext, query: str) -> List[Union[Goal, Memory]]:
    query_embedding = get_embedding(ctx.embedding_model, query)

    relevant_memories = [
        memory
        for memory in ctx.db.query_vector(ctx.l2_memory_relevance_distance_threshold, Memory, ctx.user_id, query_embedding)
        if isinstance(memory, Memory)
    ]

    relevant_goals = [
        goal
        for goal in ctx.db.query_vector(ctx.l2_memory_relevance_distance_threshold, Goal, ctx.user_id, query_embedding)
        if isinstance(goal, Goal)
    ]

    return relevant_memories + relevant_goals


def get_memory_by_name(ctx: ElroyContext, memory_name: str) -> Optional[Memory]:
    return ctx.db.exec(
        select(Memory).where(
            Memory.user_id == ctx.user_id,
            Memory.name == memory_name,
            Memory.is_active == True,
        )
    ).first()


@tracer.chain
def get_relevant_memory_context_msgs(ctx: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    message_content = pipe(
        context_messages,
        remove(lambda x: x.role == SYSTEM),
        tail(4),
        map(lambda x: f"{x.role}: {x.content}" if x.content else None),
        remove(lambda x: x is None),
        list,
        "\n".join,
    )

    if not message_content:
        return []

    assert isinstance(message_content, str)

    new_recalled_memories: List[EmbeddableSqlModel] = pipe(
        message_content,
        partial(get_embedding, ctx.embedding_model),
        lambda x: juxt(get_most_relevant_goal, get_most_relevant_memory)(ctx, x),
        filter(lambda x: x is not None),
        remove(partial(is_in_context, context_messages)),
        list,
    )  # type: ignore

    if not new_recalled_memories:
        return []
    elif ctx.reflect:
        return get_reflective_recall(ctx, context_messages, new_recalled_memories)
    else:
        return get_fast_recall(new_recalled_memories)


@tracer.chain
def get_fast_recall(memories: Iterable[EmbeddableSqlModel]) -> List[ContextMessage]:
    """Add recalled content to context, unprocessed."""
    return pipe(
        memories,
        map(
            lambda x: ContextMessage(
                role=SYSTEM,
                memory_metadata=[RecalledMemoryMetadata(memory_type=x.__class__.__name__, id=x.id, name=x.get_name())],
                content="Information recalled from assistant memory: " + x.to_fact(),
                chat_model=None,
            )
        ),
        list,
    )  # type: ignore


@tracer.chain
def get_reflective_recall(
    ctx: ElroyContext, context_messages: Iterable[ContextMessage], memories: Iterable[EmbeddableSqlModel]
) -> List[ContextMessage]:
    """More process memory into more reflective recall message"""
    output: str = pipe(
        memories,
        map(lambda x: x.to_fact()),
        "\n\n".join,
        lambda x: "Recalled Memory Content\n\n"
        + x
        + "#Converstaion Transcript:\n"
        + format_context_messages(tail(3, list(context_messages)[1:]), get_user_preferred_name(ctx), get_assistant_name(ctx)),  # type: ignore
        lambda x: query_llm(
            ctx.chat_model,
            x,
            """#Identity and Purpose

        I am the internal thoughts of an AI assistant. I am reflecting on memories that have entered my awareness.

        I am considering recalled context, as well as the transcript of a recent conversation. I am:
        - Re-stating the most relevant context from the recalled content
        - Reflecting on how the recalled content relates to the conversation transcript

        Specific examples are most helpful. For example, if the recalled content is:

        "USER mentioned that when playing basketball, they struggle to remember to follow through on their shots."

        and the conversation transcript includes:
        "USER: I'm going to play basketball next week"

        a good response would be:
        "I remember that USER struggles to remember to follow through on their shots when playing basketball. I should remind USER about following through on their shots for next week's game."


        My response will be in the first person, and will be transmitted to an AI assistant to inform their response. My response will NOT be transmitted to the user.

        My response is brief and to the point, no more than 100 words.
        """,
        ),
    )  # type: ignore

    return [
        ContextMessage(
            role=SYSTEM,
            content="\n".join(
                [output, "\nThis recollection was based on the following Goals and Memories:"]
                + [x.__class__.__name__ + ": " + x.get_name() for x in memories]
            ),
            chat_model=ctx.chat_model.name,
            memory_metadata=[to_recalled_memory_metadata(x) for x in memories],
        )
    ]


def get_in_context_memories_metadata(context_messages: Iterable[ContextMessage]) -> List[str]:
    return pipe(
        context_messages,
        map(lambda m: m.memory_metadata),
        filter(lambda m: m is not None),
        concat,
        map(lambda m: f"{m.memory_type}: {m.name}"),
        unique,
        list,
        sorted,
    )  # type: ignore
