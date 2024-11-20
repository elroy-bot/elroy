import hashlib
import logging
from functools import partial
from typing import Iterable, List, Tuple, Type, TypeVar

from sqlalchemy.orm import aliased
from sqlmodel import func, select
from toolz import compose, pipe
from toolz.curried import do, map

from ..config.config import ElroyContext
from ..config.constants import RESULT_SET_LIMIT_COUNT
from ..repository.data_models import EmbeddableSqlModel, Goal, Memory
from ..repository.facts import to_fact
from ..utils.utils import first_or_none

T = TypeVar("T", bound=EmbeddableSqlModel)


def query_vector(
    table: Type[EmbeddableSqlModel],
    context: ElroyContext,
    query: List[float],
) -> Iterable[EmbeddableSqlModel]:
    """
    Perform a vector search on the specified table using the given query.

    Args:
        query (str): The search query.
        table (EmbeddableSqlModel): The SQLModel table to search.

    Returns:
        List[Tuple[Fact, float]]: A list of tuples containing the matching Fact and its similarity score.
    """

    distance_exp = table.embedding.l2_distance(query)  # type: ignore

    return pipe(
        context.session.exec(
            select(table, distance_exp.label("distance"))  # type: ignore
            .where(
                table.user_id == context.user_id,
                table.is_active == True,
                distance_exp < context.config.l2_memory_relevance_distance_threshold,  # type: ignore
                table.embedding != None,
            )
            .order_by(distance_exp)
            .limit(RESULT_SET_LIMIT_COUNT)
        ),
        map(lambda row: row[0]),
    )


get_most_relevant_goal = compose(first_or_none, partial(query_vector, Goal))
get_most_relevant_memory = compose(first_or_none, partial(query_vector, Memory))


T = TypeVar("T", bound=EmbeddableSqlModel)


def find_redundant_pairs(
    context: ElroyContext,
    table: Type[T],
    limit: int = 1,
) -> Iterable[Tuple[T, T]]:
    """
    Query an EmbeddableSqlModel using a self-join and return the closest pair of rows in similarity
    over the L2_PERCENT_CLOSER_THAN_RANDOM_THRESHOLD.

    Args:
        context (ElroyContext): The Elroy context.
        table (Type[EmbeddableSqlModel]): The table to query.
        filter_clause (Any, optional): Additional filter clause. Defaults to lambda: True.

    Returns:
        Optional[Tuple[EmbeddableSqlModel, EmbeddableSqlModel, float]]:
        A tuple containing the two closest rows and their similarity score,
        or None if no pair is found above the threshold.
    """
    t1 = aliased(table, name="t1")
    t2 = aliased(table, name="t2")

    distance_exp = t1.embedding.l2_distance(t2.embedding)  # type: ignore

    yield from pipe(
        context.session.exec(
            select(t1, t2, distance_exp.label("distance"))  # type: ignore
            .join(t2, t1.id < t2.id)  # type: ignore Ensure we don't compare a row with itself or duplicate comparisons
            .where(
                t1.user_id == context.user_id,
                t2.user_id == context.user_id,
                t1.is_active == True,
                t2.is_active == True,
                distance_exp < context.config.l2_memory_consolidation_distance_threshold,  # type: ignore
                t1.embedding.is_not(None),  # type: ignore
                t2.embedding.is_not(None),  # type: ignore
            )
            .order_by(func.random())  # order by random to lessen chance of infinite loops
            .limit(limit)
        ),
        map(do(lambda row: logging.info(f"Found redundant pair: {row[0].id} and {row[1].id}. Distance = {row[2]}"))),
        map(lambda row: (row[0], row[1])),
    )


def upsert_embedding(context: ElroyContext, row: EmbeddableSqlModel) -> None:
    from ..llm.client import get_embedding

    new_text = to_fact(row)
    new_md5 = hashlib.md5(new_text.encode()).hexdigest()

    if row.embedding_text_md5 == new_md5:
        logging.info("Old and new text matches md5, skipping")
        return
    else:
        embedding = get_embedding(context.config.embedding_model, new_text)

        row.embedding = embedding
        row.embedding_text_md5 = new_md5

        context.session.add(row)
        context.session.commit()
