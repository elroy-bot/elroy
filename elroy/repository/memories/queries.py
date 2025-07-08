import json
from functools import partial
from typing import Callable, Iterable, List, Optional, Sequence, TypeVar, Union

from pydantic import BaseModel
from sqlmodel import select
from toolz import concat, juxt, pipe, unique
from toolz.curried import filter, map, remove, tail, do

from ...config.llm import ChatModel
from ...core.constants import SYSTEM
from ...core.ctx import ElroyContext
from ...core.tracing import tracer
from ...db.db_models import (
    EmbeddableSqlModel,
    Goal,
    Memory,
    MemorySource,
    get_memory_source_class,
)
from ...llm.client import get_embedding, query_llm, query_llm_with_response_format
from ..context_messages.data_models import ContextMessage, RecalledMemoryMetadata
from ..context_messages.transforms import (
    ContextMessageSetWithMessages,
    format_context_messages,
)
from ..recall.queries import (
    get_most_relevant_goals,
    get_most_relevant_memories,
    is_in_context,
)
from ..recall.transforms import to_recalled_memory_metadata
from ..user.queries import do_get_user_preferred_name, get_assistant_name


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
def get_relevant_memories_and_goals(ctx: ElroyContext, query: str) -> List[Union[Goal, Memory]]:
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


T = TypeVar("T")


@tracer.chain
def filter_for_relevance(
    model: ChatModel,
    query: str,
    memories: List[T],
    extraction_fn: Callable[[T], str],
) -> List[T]:

    memories_str = "\n\n".join(f"{i}. {extraction_fn(memory)}" for i, memory in enumerate(memories))

    class RelevanceResponse(BaseModel):
        answers: List[bool]
        reasoning: str  # noqa: F841

    resp = query_llm_with_response_format(
        model=model,
        prompt=f"""
        Query: {query}
        Responses:
        {memories_str}
        """,
        system="""Your job is to determine which of a set of memories are relevant to a query.
        Given a query and a list of memories, output:
        - a list of boolean values indicating whether each memory is relevant to the query.
        - a brief explanation of your reasoning.

        """,
        response_format=RelevanceResponse,
    )

    return [mem for mem, r in zip(list(memories), resp.answers) if r]


def get_message_content(context_messages: List[ContextMessage], n: int) -> str:
    return pipe(
        context_messages,
        remove(lambda x: x.role == SYSTEM),
        remove(is_memory_message),
        tail(4),
        map(lambda x: f"{x.role}: {x.content}" if x.content else None),
        remove(lambda x: x is None),
        list,
        "\n".join,
    )


def is_memory_message(context_message: ContextMessage) -> bool:
    return context_message.memory_metadata is not None and context_message.memory_metadata != []


@tracer.chain
def get_relevant_memory_context_msgs(ctx: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    message_content = get_message_content(context_messages, 6)

    if not message_content:
        return []

    assert isinstance(message_content, str)

    return pipe(
        message_content,
        partial(get_embedding, ctx.embedding_model),
        do(ctx.status_tracker.track("Fetching memories")),
        lambda x: juxt(get_most_relevant_goals, get_most_relevant_memories)(ctx, x),
        do(ctx.status_tracker.complete("Fetching memories")),
        concat,
        list,
        filter(lambda x: x is not None),
        remove(partial(is_in_context, context_messages)),
        list,
        do(ctx.status_tracker.track("Selecting relevant memories")),
        lambda mems: filter_for_relevance(
            ctx.chat_model,
            message_content,
            mems,
            lambda m: m.to_fact(),
        ),
        do(ctx.status_tracker.complete("Selecting relevant memories")),
        list,
        lambda mems: get_reflective_recall(ctx, context_messages, mems) if ctx.reflect else get_fast_recall(mems),
    )


@tracer.chain
def get_fast_recall(memories: Iterable[EmbeddableSqlModel]) -> List[ContextMessage]:
    """Add recalled content to context, unprocessed."""
    if not memories:
        return []

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
    with ctx.status_tracker.tracking("Reflecting on memories"):
        if not memories:
            return []

        output: str = pipe(
            memories,
            map(lambda x: x.to_fact()),
            "\n\n".join,
            lambda x: "Recalled Memory Content\n\n"
            + x
            + "#Converstaion Transcript:\n"
            + format_context_messages(
                tail(3, list(context_messages)[1:]),  # type: ignore
                do_get_user_preferred_name(ctx.db.session, ctx.user_id),
                get_assistant_name(ctx),
            ),
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
