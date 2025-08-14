import json
from functools import partial
from typing import Callable, Iterable, List, Optional, Sequence, TypeVar, Union

from pydantic import BaseModel, Field
from sqlmodel import col, select
from toolz import concat, juxt, pipe, unique
from toolz.curried import filter, map, remove, tail

from ...config.llm import ChatModel
from ...core.constants import SYSTEM, TOOL
from ...core.ctx import ElroyContext
from ...core.logging import get_logger, log_execution_time
from ...core.tracing import tracer
from ...db.db_models import (
    EmbeddableSqlModel,
    Memory,
    MemorySource,
    Reminder,
    get_memory_source_class,
)
from ...llm.client import get_embedding, query_llm_with_response_format
from ...models import RecallMetadata, RecallResponse
from ..context_messages.data_models import ContextMessage
from ..context_messages.tools import to_synthetic_tool_call
from ..context_messages.transforms import (
    ContextMessageSetWithMessages,
    format_context_messages,
)
from ..recall.queries import (
    get_most_relevant_memories,
    get_most_relevant_reminders,
    get_recall_metadata,
    is_in_context,
)
from ..user.queries import do_get_user_preferred_name, get_assistant_name
from .transforms import to_fast_recall_tool_call

logger = get_logger()


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
def get_relevant_memories_and_reminders(ctx: ElroyContext, query: str) -> List[Union[Reminder, Memory]]:
    query_embedding = get_embedding(ctx.embedding_model, query)

    relevant_memories = [
        memory
        for memory in ctx.db.query_vector(ctx.l2_memory_relevance_distance_threshold, Memory, ctx.user_id, query_embedding)
        if isinstance(memory, Memory)
    ]

    relevant_reminders = [
        reminder
        for reminder in ctx.db.query_vector(ctx.l2_memory_relevance_distance_threshold, Reminder, ctx.user_id, query_embedding)
        if isinstance(reminder, Reminder)
    ]

    return relevant_memories + relevant_reminders


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
@log_execution_time
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
        remove(lambda x: x.role == TOOL),
        tail(4),
        map(lambda x: f"{x.role}: {x.content}" if x.content else None),
        remove(lambda x: x is None),
        list,
        "\n".join,
    )


@tracer.chain
def get_relevant_memory_context_msgs(ctx: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    message_content = get_message_content(context_messages, 6)

    if not message_content:
        return []

    assert isinstance(message_content, str)

    return pipe(
        message_content,
        partial(get_embedding, ctx.embedding_model),
        lambda x: juxt(get_most_relevant_memories, get_most_relevant_reminders)(ctx, x),
        concat,
        filter(lambda x: x is not None),
        remove(partial(is_in_context, context_messages)),
        list,
        lambda mems: get_reflective_recall(ctx, context_messages, mems) if ctx.reflect else get_fast_recall(mems),
    )


@tracer.chain
def get_fast_recall(memories: Iterable[EmbeddableSqlModel]) -> List[ContextMessage]:
    """Add recalled content to context, unprocessed."""
    if not memories:
        return []

    return to_fast_recall_tool_call(list(memories))


@tracer.chain
@log_execution_time
def get_reflective_recall(
    ctx: ElroyContext, context_messages: Iterable[ContextMessage], memories: Iterable[EmbeddableSqlModel]
) -> List[ContextMessage]:
    """More process memory into more reflective recall message"""
    if not memories:
        return []

    class ReflectionResponse(BaseModel):
        content: Optional[str] = Field(
            description="The content of the reflection on the memories, written in the first person. If memories are irrelevant, this field should be empty"
        )
        is_relevant: bool = Field(description="Whether or not any of the recalled information is relevant to the conversation.")

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
        lambda x: query_llm_with_response_format(
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
            response_format=ReflectionResponse,
        ),
    )  # type: ignore

    assert isinstance(output, ReflectionResponse)
    if not output.is_relevant:
        return []
    elif output.is_relevant and not output.content:
        logger.warning("Memories deemed relevant, but not content returned.")
        return []
    else:
        assert output.content
        return to_synthetic_tool_call(
            "get_reflective_recall",
            RecallResponse(
                content=output.content,
                memory_metadata=[
                    RecallMetadata(
                        memory_type=x.__class__.__name__,
                        memory_id=x.id,
                        name=x.get_name(),
                    )
                    for x in memories
                ],  # type: ignore
            ),
        )


def get_in_context_memories_metadata(context_messages: Iterable[ContextMessage]) -> List[str]:
    return pipe(
        context_messages,
        map(get_recall_metadata),
        concat,
        map(lambda m: f"{m.memory_type}: {m.name}"),
        unique,
        list,
        sorted,
    )  # type: ignore


def get_memories(ctx: ElroyContext, memory_ids: List[int]) -> List[Memory]:
    return list(ctx.db.exec(select(Memory).where(Memory.user_id == ctx.user_id, col(Memory.id).in_(memory_ids))).all())
