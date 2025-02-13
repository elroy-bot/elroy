import json
from functools import partial
from typing import Iterable, List, Optional, Sequence, Union

from sqlmodel import select
from toolz import concat, juxt, pipe, unique
from toolz.curried import filter, map, remove, tail

from ...config.constants import SYSTEM
from ...config.ctx import ElroyContext
from ...db.db_models import Goal, Memory, MemorySource, get_memory_source_class
from ...llm.client import get_embedding
from ...utils.utils import logged_exec_time
from ..context_messages.data_models import ContextMessage, RecalledMemoryMetadata
from ..context_messages.transforms import ContextMessageSetWithMessages
from ..recall.queries import (
    get_most_relevant_goal,
    get_most_relevant_memory,
    is_in_context,
)


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


@logged_exec_time
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

    new_memory_messages = pipe(
        message_content,
        partial(get_embedding, ctx.embedding_model),
        lambda x: juxt(get_most_relevant_goal, get_most_relevant_memory)(ctx, x),
        filter(lambda x: x is not None),
        remove(partial(is_in_context, context_messages)),
        map(
            lambda x: ContextMessage(
                role=SYSTEM,
                memory_metadata=[RecalledMemoryMetadata(memory_type=x.__class__.__name__, id=x.id, name=x.get_name())],
                content="Information recalled from assistant memory: " + x.to_fact(),
                chat_model=None,
            )
        ),
        list,
    )

    return new_memory_messages


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
