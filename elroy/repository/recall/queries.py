from functools import partial
from typing import Iterable, List, Type
from sqlmodel import select

from toolz import compose

from ...config.ctx import ElroyContext
from ...db.db_models import Goal, Memory
from ...utils.utils import first_or_none
from ..context_messages.data_models import ContextMessage
from .transforms import MEMORY_SOURCE_TYPES, Embeddable, MemorySource


def get_sources(ctx: ElroyContext, memory: Memory) -> List[MemorySource]:
    srcs = []
    for x in memory.get_source_metadata():
        tbl = next(y for y in MEMORY_SOURCE_TYPES if x['source_type'] == y.__name__)
        print(x)
        id = x.get('source_id') or x.get('id')
        assert id
        srcs.append(ctx.db.exec(select(tbl).where(tbl.id == id)).first())
    return srcs


def is_in_context_message(memory: Embeddable, context_message: ContextMessage) -> bool:
    if not context_message.memory_metadata:
        return False
    return any(x.memory_type == memory.__class__.__name__ and x.id == memory.id for x in context_message.memory_metadata)


def is_in_context(context_messages: List[ContextMessage], memory: Embeddable) -> bool:
    return any(is_in_context_message(memory, x) for x in context_messages)


def query_vector(
    table: Type[Embeddable],
    ctx: ElroyContext,
    query: List[float],
) -> Iterable[Embeddable]:
    """
    Perform a vector search on the specified table using the given query.

    Args:
        query (str): The search query.
        table (Embeddable): The SQLModel table to search.

    Returns:
        List[Tuple[Fact, float]]: A list of tuples containing the matching Fact and its similarity score.
    """

    return ctx.db.query_vector(
        ctx.l2_memory_relevance_distance_threshold,
        table,
        ctx.user_id,
        query,
    )


get_most_relevant_goal = compose(first_or_none, partial(query_vector, Goal))
get_most_relevant_memory = compose(first_or_none, partial(query_vector, Memory))
