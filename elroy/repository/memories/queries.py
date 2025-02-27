import json
from functools import partial
from typing import Iterable, List, Optional, Sequence, Union

from sqlmodel import select
from toolz import concat, juxt, pipe, unique
from toolz.curried import filter, map, remove, tail

from ...config.constants import SYSTEM
from ...config.ctx import ElroyContext
from ...db.db_models import (
    EmbeddableSqlModel,
    Goal,
    Memory,
    MemorySource,
    get_memory_source_class,
)
from ...llm.client import generate_chat_completion_message, get_embedding
from ...llm.stream_parser import StreamParser, collect
from ...utils.utils import logged_exec_time
from ..context_messages.data_models import ContextMessage, RecalledMemoryMetadata
from ..context_messages.transforms import ContextMessageSetWithMessages
from ..recall.queries import (
    get_most_relevant_goal,
    get_most_relevant_memory,
    is_in_context,
)
from ..recall.transforms import to_recalled_memory_metadata


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


@logged_exec_time
def get_reflective_recall(
    ctx: ElroyContext, context_messages: Iterable[ContextMessage], memories: Iterable[EmbeddableSqlModel]
) -> List[ContextMessage]:
    """More process memory into more reflective recall message"""
    stream: StreamParser = pipe(
        memories,
        map(lambda x: x.to_fact()),
        "\n\n".join,
        lambda x: f"You are an internal thought process of an AI assistant. Consider the following content recalled from memory. "
        "Return an internal thought monologue for what is signficant about the recalled content, and how it might related to the conversation. "
        "Your response should be in the voice of the internal reflections of the AI assistant, do not address the user."
        "The content of the recalled memories are as follows:\n" + x,
        lambda x: ContextMessage(
            role=SYSTEM,
            content=x,
            chat_model=None,
        ),
        lambda x: [x] + list(context_messages)[1:],
        lambda x: generate_chat_completion_message(ctx.chat_model, x, [], False),
    )

    collect(stream.process_stream())

    return [
        ContextMessage(
            role=SYSTEM,
            content="\n".join(
                [stream.get_full_text(), "\nThis recollection was based on the following Goals and Memories:"]
                + [x.__class__.__name__ + ": " + x.get_name() for x in memories]
            ),
            chat_model=None,
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
