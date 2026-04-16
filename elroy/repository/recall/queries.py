from collections.abc import Iterable
from typing import TypeVar

from pydantic import ValidationError
from toolz import identity, pipe
from toolz.curried import filter

from ...core.configs import MemoryConfig
from ...core.constants import TOOL
from ...core.ctx import ElroyContext
from ...core.logging import log_execution_time
from ...db.db_models import AgendaItem, EmbeddableSqlModel, Memory
from ...db.db_session import DbSession
from ...repository.data_models import RecallMetadata, RecallResponse
from ..context_messages.data_models import ContextMessage


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


def _store(ctx: ElroyContext) -> RecallReadStore:
    return RecallReadStore(ctx.db, ctx.user_id, ctx.memory_config)


def query_vector[T: EmbeddableSqlModel](table: type[T], ctx: ElroyContext, query: list[float]) -> Iterable[T]:
    """
    Perform a vector search on the specified table using the given query.

    Args:
        query (str): The search query.
        table (EmbeddableSqlModel): The SQLModel table to search.

    Returns:
        List[Tuple[Fact, float]]: A list of tuples containing the matching Fact and its similarity score.
    """
    return _store(ctx).query_vector(table, query)


@log_execution_time
def get_most_relevant_memories(ctx: ElroyContext, query: list[float]) -> list[Memory]:
    """Get the most relevant memory for the given query."""
    return _store(ctx).get_most_relevant_memories(query)


@log_execution_time
def get_most_relevant_due_items(ctx: ElroyContext, query: list[float]) -> list[AgendaItem]:
    return _store(ctx).get_most_relevant_due_items(query)


@log_execution_time
def get_most_relevant_agenda_items(ctx: ElroyContext, query: list[float]) -> list[AgendaItem]:
    return _store(ctx).get_most_relevant_agenda_items(query)
