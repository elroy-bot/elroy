import json
from collections.abc import Callable, Iterable, Sequence
from functools import partial
from typing import Any, TypeVar, cast

from pydantic import BaseModel, Field
from sqlmodel import col, select
from toolz import concat, pipe, unique
from toolz.curried import filter, map, remove, tail

from ...core.configs import MemoryConfig
from ...core.constants import SYSTEM, TOOL
from ...core.ctx import ElroyContext
from ...core.logging import get_logger, log_execution_time
from ...db.db_models import (
    AgendaItem,
    EmbeddableSqlModel,
    Memory,
    MemorySource,
    get_memory_source_class,
)
from ...db.db_session import DbSession
from ...llm.client import LlmClient
from ..context_messages.data_models import ContextMessage
from ..context_messages.tools import to_synthetic_tool_call
from ..context_messages.transforms import (
    ContextMessageSetWithMessages,
    format_context_messages,
)
from ..data_models import RecallMetadata, RecallResponse
from ..recall.queries import (
    get_recall_metadata,
    is_in_context,
)
from ..user.queries import do_get_user_preferred_name, get_assistant_name
from .transforms import to_fast_recall_tool_call

logger = get_logger()

T = TypeVar("T")


class MemoryQueryService:
    def __init__(self, db: DbSession, user_id: int, memory_config: MemoryConfig, llm: LlmClient, reflect: bool):
        self.db = db
        self.user_id = user_id
        self.memory_config = memory_config
        self.llm = llm
        self.reflect = reflect

    def db_get_memory_source_by_name(self, source_type: str, name: str) -> MemorySource | None:
        source_class = get_memory_source_class(source_type)

        if source_class == ContextMessageSetWithMessages:
            return ContextMessageSetWithMessages(self.db.session, int(name), self.user_id)
        if hasattr(source_class, "name"):
            return self.db.exec(select(source_class).where(source_class.name == name, source_class.user_id == self.user_id)).first()
        raise NotImplementedError(f"Cannot get source of type {source_type}")

    def db_get_memory_source(self, source_type: str, id: int) -> MemorySource | None:
        source_class = get_memory_source_class(source_type)

        if source_class == ContextMessageSetWithMessages:
            return ContextMessageSetWithMessages(self.db.session, id, self.user_id)
        return self.db.exec(select(source_class).where(source_class.id == id, source_class.user_id == self.user_id)).first()

    def db_get_source_list_for_memory(self, memory: Memory) -> Sequence[MemorySource]:
        if not memory.source_metadata:
            return []
        return pipe(
            memory.source_metadata,
            json.loads,
            map(lambda x: self.db_get_memory_source(x["source_type"], x["id"])),
            remove(lambda x: x is None),
            list,
        )

    def get_active_memories(self) -> list[Memory]:
        return list(
            self.db.exec(
                select(Memory).where(
                    Memory.user_id == self.user_id,
                    cast(Any, Memory.is_active),
                )
            ).all()
        )

    def get_relevant_memories_and_due_items(self, query: str) -> list[Memory | AgendaItem]:
        query_embedding = self.llm.get_embedding(query)

        relevant_memories = [
            memory
            for memory in self.db.query_vector(
                self.memory_config.l2_memory_relevance_distance_threshold,
                Memory,
                self.user_id,
                query_embedding,
            )
            if isinstance(memory, Memory)
        ]

        relevant_due_items = list(
            self.db.query_vector(
                self.memory_config.l2_memory_relevance_distance_threshold,
                AgendaItem,
                self.user_id,
                query_embedding,
            )
        )
        relevant_due_items = [item for item in relevant_due_items if item.trigger_datetime or item.trigger_context][:2]

        return relevant_memories + relevant_due_items

    def get_memory_by_name(self, memory_name: str) -> Memory | None:
        return self.db.exec(
            select(Memory).where(
                Memory.user_id == self.user_id,
                Memory.name == memory_name,
                cast(Any, Memory.is_active),
            )
        ).first()

    def get_relevant_memory_context_msgs(
        self,
        context_messages: list[ContextMessage],
        assistant_name: str,
        user_preferred_name: str | None,
    ) -> list[ContextMessage]:
        message_content = get_message_content(context_messages, 6)

        if not message_content:
            return []

        relevant_items = pipe(
            message_content,
            self.llm.get_embedding,
            lambda x: concat(
                [
                    get_most_relevant_memories_from_db(self.db, self.user_id, self.memory_config, x),
                    get_most_relevant_due_items_from_db(self.db, self.user_id, self.memory_config, x),
                    get_most_relevant_agenda_items_from_db(self.db, self.user_id, self.memory_config, x),
                ]
            ),
            filter(lambda x: x is not None),
            remove(partial(is_in_context, context_messages)),
            list,
        )

        if self.reflect:
            return get_reflective_recall_from_service(
                self.llm,
                context_messages,
                relevant_items,
                assistant_name,
                user_preferred_name,
            )
        return get_fast_recall(relevant_items)

    def get_memories(self, memory_ids: list[int]) -> list[Memory]:
        return list(self.db.exec(select(Memory).where(Memory.user_id == self.user_id, col(Memory.id).in_(memory_ids))).all())


def _service(ctx: ElroyContext) -> MemoryQueryService:
    return MemoryQueryService(ctx.db, ctx.user_id, ctx.memory_config, ctx.llm, ctx.reflect)


def db_get_memory_source_by_name(ctx: ElroyContext, source_type: str, name: str) -> MemorySource | None:
    return _service(ctx).db_get_memory_source_by_name(source_type, name)


def db_get_source_list_for_memory(ctx: ElroyContext, memory: Memory) -> Sequence[MemorySource]:
    return _service(ctx).db_get_source_list_for_memory(memory)


def db_get_memory_source(ctx: ElroyContext, source_type: str, id: int) -> MemorySource | None:
    return _service(ctx).db_get_memory_source(source_type, id)


def get_active_memories(ctx: ElroyContext) -> list[Memory]:
    return _service(ctx).get_active_memories()


def get_relevant_memories_and_due_items(ctx: ElroyContext, query: str) -> list[Memory | AgendaItem]:
    return _service(ctx).get_relevant_memories_and_due_items(query)


def get_memory_by_name(ctx: ElroyContext, memory_name: str) -> Memory | None:
    return _service(ctx).get_memory_by_name(memory_name)


@log_execution_time
def filter_for_relevance(
    fast_llm: LlmClient,
    query: str,
    memories: list[T],
    extraction_fn: Callable[[T], str],
) -> list[T]:
    """Filter memories for relevance using fast model for efficiency."""

    memories_str = "\n\n".join(f"{i}. {extraction_fn(memory)}" for i, memory in enumerate(memories))

    class RelevanceResponse(BaseModel):
        answers: list[bool]
        reasoning: str

    resp = fast_llm.query_llm_with_response_format(
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

    return [mem for mem, r in zip(list(memories), resp.answers, strict=False) if r]


def get_message_content(context_messages: list[ContextMessage], n: int) -> str:
    return pipe(
        context_messages,
        remove(lambda x: x.role == SYSTEM),
        remove(lambda x: x.role == TOOL),
        tail(n),
        map(lambda x: f"{x.role}: {x.content}" if x.content else None),
        remove(lambda x: x is None),
        list,
        "\n".join,
    )


def get_relevant_memory_context_msgs(ctx: ElroyContext, context_messages: list[ContextMessage]) -> list[ContextMessage]:
    return _service(ctx).get_relevant_memory_context_msgs(
        context_messages,
        get_assistant_name(ctx),
        do_get_user_preferred_name(ctx.db.session, ctx.user_id),
    )


def get_fast_recall(memories: Iterable[EmbeddableSqlModel]) -> list[ContextMessage]:
    """Add recalled content to context, unprocessed."""
    if not memories:
        return []

    return to_fast_recall_tool_call(list(memories))


@log_execution_time
def get_reflective_recall(
    ctx: ElroyContext,
    context_messages: Iterable[ContextMessage],
    memories: Iterable[EmbeddableSqlModel],
) -> list[ContextMessage]:
    return get_reflective_recall_from_service(
        ctx.llm,
        context_messages,
        memories,
        get_assistant_name(ctx),
        do_get_user_preferred_name(ctx.db.session, ctx.user_id),
    )


def get_reflective_recall_from_service(
    llm: LlmClient,
    context_messages: Iterable[ContextMessage],
    memories: Iterable[EmbeddableSqlModel],
    assistant_name: str,
    user_preferred_name: str | None,
) -> list[ContextMessage]:
    """Process memory into a reflective recall message."""
    memories_list = list(memories)
    if not memories_list:
        return []

    class ReflectionResponse(BaseModel):
        content: str | None = Field(
            description="The content of the reflection on the memories, written in the first person. If memories are irrelevant, this field should be empty"
        )
        is_relevant: bool = Field(description="Whether or not any of the recalled information is relevant to the conversation.")

    output = pipe(
        memories_list,
        map(lambda x: x.to_fact()),
        "\n\n".join,
        lambda x: (
            "Recalled Memory Content\n\n"
            + x
            + "#Converstaion Transcript:\n"
            + format_context_messages(
                tail(3, list(context_messages)[1:]),
                user_preferred_name or "User",
                assistant_name,
            )
        ),
        lambda x: llm.query_llm_with_response_format(
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
    )

    assert isinstance(output, ReflectionResponse)
    if not output.is_relevant:
        return []
    if output.is_relevant and not output.content:
        logger.warning("Memories deemed relevant, but not content returned.")
        return []
    assert output.content
    return to_synthetic_tool_call(
        "get_reflective_recall",
        RecallResponse(content=output.content, recall_metadata=_build_recall_metadata(cast(list[MemorySource], memories_list))),
    )


def _build_recall_metadata(memories: list[MemorySource]) -> list[RecallMetadata]:
    recall_metadata: list[RecallMetadata] = []
    for memory in memories:
        memory_id = memory.id
        assert memory_id is not None
        recall_metadata.append(
            RecallMetadata(
                memory_type=memory.__class__.__name__,
                memory_id=memory_id,
                name=memory.get_name(),
            )
        )
    return recall_metadata


def get_in_context_memories_metadata(context_messages: Iterable[ContextMessage]) -> list[str]:
    return pipe(
        context_messages,
        map(get_recall_metadata),
        concat,
        map(lambda m: f"{m.memory_type}: {m.name}"),
        unique,
        list,
        sorted,
    )


def get_memories(ctx: ElroyContext, memory_ids: list[int]) -> list[Memory]:
    return _service(ctx).get_memories(memory_ids)


def get_most_relevant_memories_from_db(
    db: DbSession,
    user_id: int,
    memory_config: MemoryConfig,
    query: list[float],
) -> list[Memory]:
    return [
        item
        for item in db.query_vector(memory_config.l2_memory_relevance_distance_threshold, Memory, user_id, query)
        if isinstance(item, Memory)
    ][:2]


def get_most_relevant_due_items_from_db(
    db: DbSession,
    user_id: int,
    memory_config: MemoryConfig,
    query: list[float],
) -> list[AgendaItem]:
    return [
        item
        for item in db.query_vector(memory_config.l2_memory_relevance_distance_threshold, AgendaItem, user_id, query)
        if isinstance(item, AgendaItem) and (item.trigger_datetime or item.trigger_context)
    ][:2]


def get_most_relevant_agenda_items_from_db(
    db: DbSession,
    user_id: int,
    memory_config: MemoryConfig,
    query: list[float],
) -> list[AgendaItem]:
    return [
        item
        for item in db.query_vector(memory_config.l2_memory_relevance_distance_threshold, AgendaItem, user_id, query)
        if isinstance(item, AgendaItem) and not (item.trigger_datetime or item.trigger_context)
    ][:2]
