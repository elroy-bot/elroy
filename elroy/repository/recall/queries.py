from collections.abc import Iterable
from typing import TypeVar

from pydantic import ValidationError
from toolz import identity, pipe
from toolz.curried import filter

from ...core.configs import MemoryConfig
from ...core.constants import TOOL
from ...core.ctx import ElroyConfig
from ...core.logging import log_execution_time
from ...core.session import run_with_turn
from ...core.turn import TurnContext
from ...db.db_models import AgendaItem, EmbeddableSqlModel, Memory
from ...db.db_session import DbSession
from ...repository.data_models import RecallMetadata, RecallResponse
from ..context_messages.data_models import ContextMessage
from ..user.session import build_user_session
from .runtime import build_recall_runtime


def get_recall_metadata(context_message: ContextMessage, recall_type: type[EmbeddableSqlModel] | None = None) -> list[RecallMetadata]:
    if context_message.role != TOOL or not context_message.content:
        return []
    try:
        return pipe(
            context_message.content,
            RecallResponse.model_validate_json,
            lambda x: x.recall_metadata,
            filter(lambda m: m.memory_type == recall_type.__name__) if recall_type else identity,
            list,
        )
    except ValidationError:
        return []


def is_in_context_message(memory: EmbeddableSqlModel, context_message: ContextMessage) -> bool:
    return any(r.memory_id == memory.id and r.memory_type == memory.__class__.__name__ for r in get_recall_metadata(context_message))


def is_in_context(context_messages: Iterable[ContextMessage], memory: EmbeddableSqlModel) -> bool:
    return any(is_in_context_message(memory, x) for x in context_messages)


T = TypeVar("T", bound=EmbeddableSqlModel)


class RecallReadStore:
    def __init__(self, db: DbSession, user_id: int, memory_config: MemoryConfig):
        self.db = db
        self.user_id = user_id
        self.memory_config = memory_config

    def query_vector(self, table: type[T], query: list[float]) -> Iterable[T]:
        return list(
            self.db.query_vector(
                self.memory_config.l2_memory_relevance_distance_threshold,
                table,
                self.user_id,
                query,
            )
        )

    def get_most_relevant_memories(self, query: list[float]) -> list[Memory]:
        return list(self.query_vector(Memory, query))[:2]

    def get_most_relevant_due_items(self, query: list[float]) -> list[AgendaItem]:
        return [item for item in self.query_vector(AgendaItem, query) if item.trigger_datetime or item.trigger_context][:2]

    def get_most_relevant_agenda_items(self, query: list[float]) -> list[AgendaItem]:
        return [item for item in self.query_vector(AgendaItem, query) if not (item.trigger_datetime or item.trigger_context)][:2]


def _store(turn: TurnContext) -> RecallReadStore:
    user_session = build_user_session(turn)
    return RecallReadStore(user_session.db, user_session.user_id, build_recall_runtime(turn).memory_config)


def do_query_vector[T: EmbeddableSqlModel](turn: TurnContext, table: type[T], query: list[float]) -> Iterable[T]:
    return _store(turn).query_vector(table, query)


@log_execution_time
def do_get_most_relevant_memories(turn: TurnContext, query: list[float]) -> list[Memory]:
    return _store(turn).get_most_relevant_memories(query)


@log_execution_time
def do_get_most_relevant_due_items(turn: TurnContext, query: list[float]) -> list[AgendaItem]:
    return _store(turn).get_most_relevant_due_items(query)


@log_execution_time
def do_get_most_relevant_agenda_items(turn: TurnContext, query: list[float]) -> list[AgendaItem]:
    return _store(turn).get_most_relevant_agenda_items(query)


def query_vector[T: EmbeddableSqlModel](table: type[T], ctx: ElroyConfig, query: list[float]) -> Iterable[T]:
    return run_with_turn(ctx, do_query_vector, table, query)


@log_execution_time
def get_most_relevant_memories(ctx: ElroyConfig, query: list[float]) -> list[Memory]:
    return run_with_turn(ctx, do_get_most_relevant_memories, query)


@log_execution_time
def get_most_relevant_due_items(ctx: ElroyConfig, query: list[float]) -> list[AgendaItem]:
    return run_with_turn(ctx, do_get_most_relevant_due_items, query)


@log_execution_time
def get_most_relevant_agenda_items(ctx: ElroyConfig, query: list[float]) -> list[AgendaItem]:
    return run_with_turn(ctx, do_get_most_relevant_agenda_items, query)
