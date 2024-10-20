import hashlib
import logging
from dataclasses import dataclass
from functools import partial
from typing import Any, Generic, Iterable, List, Optional, Type, TypeVar

from sqlmodel import Session, select
from toolz import pipe
from toolz.curried import filter, map

from elroy.config import ElroyContext
from elroy.store.data_models import EmbeddableSqlModel, Goal, Memory
from elroy.system.parameters import (L2_PERCENT_CLOSER_THAN_RANDOM_THRESHOLD,
                                     L2_RANDOM_WORD_DISTANCE,
                                     RESULT_SET_LIMIT_COUNT)


def l2_percent_closer_than_random(l2_distance: float) -> float:
    """The similarity score to use with cutoffs. Measures what % closer the query is than a random sentence."""
    return round(100 * (L2_RANDOM_WORD_DISTANCE - l2_distance) / L2_RANDOM_WORD_DISTANCE, 1)


T = TypeVar("T", bound=EmbeddableSqlModel)


@dataclass
class VectorResultMatch(Generic[T]):
    result: T
    percent_closer_than_random: float


def query_vector(
    context: ElroyContext,
    query: List[float],
    table: Type[EmbeddableSqlModel],
    filter_clause: Any = lambda: True,
) -> Iterable[VectorResultMatch]:
    """
    Perform a vector search on the specified table using the given query.

    Args:
        query (str): The search query.
        table (EmbeddableSqlModel): The SQLModel table to search.

    Returns:
        List[Tuple[Fact, float]]: A list of tuples containing the matching Fact and its similarity score.
    """

    return pipe(
        context.session.exec(
            select(table, table.embedding.l2_distance(query).label("distance"))  # type: ignore
            .where(
                table.user_id == context.user_id,
                filter_clause,
                table.embedding != None,
            )
            .order_by("distance")
            .limit(RESULT_SET_LIMIT_COUNT)
        ).all(),
        map(
            lambda row: VectorResultMatch(
                row[0],
                l2_percent_closer_than_random(row[1]),
            )
        ),
    )


def get_vector_matches_over_threshold(
    context: ElroyContext, query: List[float], table: Type[EmbeddableSqlModel], filter_clause: Any = lambda: True
) -> Iterable[VectorResultMatch]:
    return pipe(
        query_vector(context, query, table, filter_clause),
        filter(lambda row: row.percent_closer_than_random > L2_PERCENT_CLOSER_THAN_RANDOM_THRESHOLD),
    )


def get_closest_vector_match(
    context: ElroyContext, query: List[float], table: Type[EmbeddableSqlModel], filter_clause: Any = lambda: True
) -> Optional[EmbeddableSqlModel]:
    return pipe(
        get_vector_matches_over_threshold(context, query, table, filter_clause),
        lambda x: next(x, None),
        lambda x: x.result if x else None,
    )  # type: ignore


get_most_relevant_goal = partial(get_closest_vector_match, table=Goal, filter_clause=Goal.is_active == True)
get_most_relevant_memory = partial(get_closest_vector_match, table=Memory)


def upsert_embedding(session: Session, row: EmbeddableSqlModel) -> None:
    from elroy.llm.client import get_embedding

    new_text = row.to_fact()
    new_md5 = hashlib.md5(new_text.encode()).hexdigest()

    if row.embedding_text_md5 == new_md5:
        logging.info("Old and new text matches md5, skipping")
        return
    else:
        embedding = get_embedding(new_text)

        row.embedding = embedding
        row.embedding_text_md5 = new_md5

        session.add(row)
        session.commit()
