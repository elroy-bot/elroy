import json
from collections.abc import Callable, Iterable, Sequence
from typing import Any, TypeVar, cast

from pydantic import BaseModel
from sqlmodel import col, select
from toolz import pipe
from toolz.curried import map, remove

from ...core.ctx import ElroyContext
from ...core.logging import log_execution_time
from ...db.db_models import (
    AgendaItem,
    Memory,
    MemorySource,
    get_memory_source_class,
)
from ...db.db_session import DbSession
from ...llm.client import LlmClient
from ..context_messages.data_models import ContextMessage
from ..context_messages.transforms import ContextMessageSetWithMessages
from ..user.queries import do_get_user_preferred_name, get_assistant_name
from .memory_recall_builder import MemoryRecallBuilder
from .memory_recall_orchestrator import MemoryRecallOrchestrator

T = TypeVar("T")


class MemoryReadStore:
    def __init__(self, db: DbSession, user_id: int):
        self.db = db
        self.user_id = user_id

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

    def get_memory_by_name(self, memory_name: str) -> Memory | None:
        return self.db.exec(
            select(Memory).where(
                Memory.user_id == self.user_id,
                Memory.name == memory_name,
                cast(Any, Memory.is_active),
            )
        ).first()

    def get_memories(self, memory_ids: list[int]) -> list[Memory]:
        return list(self.db.exec(select(Memory).where(Memory.user_id == self.user_id, col(Memory.id).in_(memory_ids))).all())


def _store(ctx: ElroyContext) -> MemoryReadStore:
    return MemoryReadStore(ctx.db, ctx.user_id)


def _recall_builder() -> MemoryRecallBuilder:
    return MemoryRecallBuilder()


def _recall_orchestrator(ctx: ElroyContext) -> MemoryRecallOrchestrator:
    return MemoryRecallOrchestrator(
        db=ctx.db,
        user_id=ctx.user_id,
        memory_config=ctx.memory_config,
        llm=ctx.llm,
        reflect=ctx.reflect,
        recall_builder=_recall_builder(),
    )


def db_get_memory_source_by_name(ctx: ElroyContext, source_type: str, name: str) -> MemorySource | None:
    return _store(ctx).db_get_memory_source_by_name(source_type, name)


def db_get_source_list_for_memory(ctx: ElroyContext, memory: Memory) -> Sequence[MemorySource]:
    return _store(ctx).db_get_source_list_for_memory(memory)


def db_get_memory_source(ctx: ElroyContext, source_type: str, id: int) -> MemorySource | None:
    return _store(ctx).db_get_memory_source(source_type, id)


def get_active_memories(ctx: ElroyContext) -> list[Memory]:
    return _store(ctx).get_active_memories()


def get_relevant_memories_and_due_items(ctx: ElroyContext, query: str) -> list[Memory | AgendaItem]:
    return _recall_orchestrator(ctx).get_relevant_memories_and_due_items(query)


def get_memory_by_name(ctx: ElroyContext, memory_name: str) -> Memory | None:
    return _store(ctx).get_memory_by_name(memory_name)


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
    return _recall_builder().get_message_content(context_messages, n)


def get_relevant_memory_context_msgs(ctx: ElroyContext, context_messages: list[ContextMessage]) -> list[ContextMessage]:
    return _recall_orchestrator(ctx).get_relevant_memory_context_msgs(
        context_messages,
        get_assistant_name(ctx),
        do_get_user_preferred_name(ctx.db.session, ctx.user_id),
    )


@log_execution_time
def get_reflective_recall(
    ctx: ElroyContext,
    context_messages: Iterable[ContextMessage],
    memories: Iterable[Any],
) -> list[ContextMessage]:
    return _recall_builder().build_reflective_recall(
        ctx.llm,
        context_messages,
        memories,
        get_assistant_name(ctx),
        do_get_user_preferred_name(ctx.db.session, ctx.user_id),
    )


def get_reflective_recall_from_service(
    llm: LlmClient,
    context_messages: Iterable[ContextMessage],
    memories: Iterable[Any],
    assistant_name: str,
    user_preferred_name: str | None,
) -> list[ContextMessage]:
    return MemoryRecallBuilder().build_reflective_recall(llm, context_messages, memories, assistant_name, user_preferred_name)


def get_in_context_memories_metadata(context_messages: Iterable[ContextMessage]) -> list[str]:
    return _recall_builder().get_in_context_memories_metadata(context_messages)


def get_memories(ctx: ElroyContext, memory_ids: list[int]) -> list[Memory]:
    return _store(ctx).get_memories(memory_ids)
