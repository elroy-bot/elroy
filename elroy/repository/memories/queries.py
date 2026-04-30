import json
from collections.abc import Callable, Iterable, Sequence
from typing import Any, TypeVar, cast

from pydantic import BaseModel
from sqlmodel import col, select
from toolz import pipe
from toolz.curried import map, remove

from ...core.ctx import ElroyConfig
from ...core.logging import log_execution_time
from ...core.session import run_with_turn
from ...core.turn import TurnContext
from ...db.db_models import AgendaItem, Memory, MemorySource, get_memory_source_class
from ...db.db_session import DbSession
from ...llm.client import LlmClient
from ..context_messages.data_models import ContextMessage
from ..context_messages.transforms import ContextMessageSetWithMessages
from ..user.queries import do_get_user_preferred_name, get_assistant_name
from ..user.session import build_user_runtime, build_user_session
from .memory_recall_builder import MemoryRecallBuilder
from .memory_recall_orchestrator import MemoryRecallOrchestrator
from .runtime import build_memory_runtime

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


def _store(turn: TurnContext) -> MemoryReadStore:
    user_session = build_user_session(turn)
    return MemoryReadStore(user_session.db, user_session.user_id)


def _recall_builder() -> MemoryRecallBuilder:
    return MemoryRecallBuilder()


def _recall_orchestrator(turn: TurnContext) -> MemoryRecallOrchestrator:
    user_session = build_user_session(turn)
    runtime = build_memory_runtime(turn)
    return MemoryRecallOrchestrator(
        db=user_session.db,
        user_id=user_session.user_id,
        memory_config=runtime.memory_config,
        llm=runtime.llm,
        reflect=runtime.reflect,
        recall_builder=_recall_builder(),
    )


def do_db_get_memory_source_by_name(turn: TurnContext, source_type: str, name: str) -> MemorySource | None:
    return _store(turn).db_get_memory_source_by_name(source_type, name)


def do_db_get_source_list_for_memory(turn: TurnContext, memory: Memory) -> Sequence[MemorySource]:
    return _store(turn).db_get_source_list_for_memory(memory)


def do_db_get_memory_source(turn: TurnContext, source_type: str, id: int) -> MemorySource | None:
    return _store(turn).db_get_memory_source(source_type, id)


def do_get_active_memories(turn: TurnContext) -> list[Memory]:
    return _store(turn).get_active_memories()


def do_get_relevant_memories_and_due_items(turn: TurnContext, query: str) -> list[Memory | AgendaItem]:
    return _recall_orchestrator(turn).get_relevant_memories_and_due_items(query)


def do_get_memory_by_name(turn: TurnContext, memory_name: str) -> Memory | None:
    return _store(turn).get_memory_by_name(memory_name)


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


def do_get_relevant_memory_context_msgs(turn: TurnContext, context_messages: list[ContextMessage]) -> list[ContextMessage]:
    user_session = build_user_session(turn)
    user_runtime = build_user_runtime(turn)
    return _recall_orchestrator(turn).get_relevant_memory_context_msgs(
        context_messages,
        get_assistant_name(user_session, user_runtime),
        do_get_user_preferred_name(user_session.db.session, user_session.user_id),
    )


@log_execution_time
def do_get_reflective_recall(
    turn: TurnContext,
    context_messages: Iterable[ContextMessage],
    memories: Iterable[Any],
) -> list[ContextMessage]:
    user_session = build_user_session(turn)
    user_runtime = build_user_runtime(turn)
    runtime = build_memory_runtime(turn)
    return _recall_builder().build_reflective_recall(
        runtime.llm,
        context_messages,
        memories,
        get_assistant_name(user_session, user_runtime),
        do_get_user_preferred_name(user_session.db.session, user_session.user_id),
    )


def build_reflective_recall(
    llm: LlmClient,
    context_messages: Iterable[ContextMessage],
    memories: Iterable[Any],
    assistant_name: str,
    user_preferred_name: str | None,
) -> list[ContextMessage]:
    return MemoryRecallBuilder().build_reflective_recall(llm, context_messages, memories, assistant_name, user_preferred_name)


def get_in_context_memories_metadata(context_messages: Iterable[ContextMessage]) -> list[str]:
    return _recall_builder().get_in_context_memories_metadata(context_messages)


def do_get_memories(turn: TurnContext, memory_ids: list[int]) -> list[Memory]:
    return _store(turn).get_memories(memory_ids)


def db_get_memory_source_by_name(ctx: ElroyConfig, source_type: str, name: str) -> MemorySource | None:
    return run_with_turn(ctx, do_db_get_memory_source_by_name, source_type, name)


def db_get_source_list_for_memory(ctx: ElroyConfig, memory: Memory) -> Sequence[MemorySource]:
    return run_with_turn(ctx, do_db_get_source_list_for_memory, memory)


def db_get_memory_source(ctx: ElroyConfig, source_type: str, id: int) -> MemorySource | None:
    return run_with_turn(ctx, do_db_get_memory_source, source_type, id)


def get_active_memories(ctx: ElroyConfig) -> list[Memory]:
    return run_with_turn(ctx, do_get_active_memories)


def get_relevant_memories_and_due_items(ctx: ElroyConfig, query: str) -> list[Memory | AgendaItem]:
    return run_with_turn(ctx, do_get_relevant_memories_and_due_items, query)


def get_memory_by_name(ctx: ElroyConfig, memory_name: str) -> Memory | None:
    return run_with_turn(ctx, do_get_memory_by_name, memory_name)


def get_relevant_memory_context_msgs(ctx: ElroyConfig, context_messages: list[ContextMessage]) -> list[ContextMessage]:
    return run_with_turn(ctx, do_get_relevant_memory_context_msgs, context_messages)


@log_execution_time
def get_reflective_recall(
    ctx: ElroyConfig,
    context_messages: Iterable[ContextMessage],
    memories: Iterable[Any],
) -> list[ContextMessage]:
    return run_with_turn(ctx, do_get_reflective_recall, context_messages, memories)


def get_memories(ctx: ElroyConfig, memory_ids: list[int]) -> list[Memory]:
    return run_with_turn(ctx, do_get_memories, memory_ids)
