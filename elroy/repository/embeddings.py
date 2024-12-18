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
from ..repository.data_models import EmbeddableSqlModel, Goal, Memory, VectorStorage
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

    # Use pgvector's <-> operator for L2 distance
    distance_exp = VectorStorage.embedding_data.l2_distance(query).label("distance")  # type: ignore

    return pipe(
        context.session.exec(
            select(table, distance_exp)
            .join(VectorStorage, (VectorStorage.source_type == table.__name__) & (VectorStorage.source_id == table.id))  # type: ignore
            .where(
                table.user_id == context.user_id,
                table.is_active == True,
                distance_exp < context.config.l2_memory_relevance_distance_threshold,
            )
            .order_by(distance_exp)
            .limit(RESULT_SET_LIMIT_COUNT)
        ),
        map(lambda row: row[0]),
    )  # type: ignore


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

    v1 = aliased(VectorStorage, name="v1")
    v2 = aliased(VectorStorage, name="v2")

    distance_exp = v1.embedding_data.l2_distance(v2.embedding_data).label("distance")  # type: ignore

    yield from pipe(
        context.session.exec(
            select(t1, t2, distance_exp)
            .join(t2, t1.id < t2.id)  # type: ignore Ensure we don't compare a row with itself
            .join(v1, (v1.source_type == table.__name__) & (v1.source_id == t1.id))  # type: ignore
            .join(v2, (v2.source_type == table.__name__) & (v2.source_id == t2.id))  # type: ignore
            .where(
                t1.user_id == context.user_id,
                t2.user_id == context.user_id,
                t1.is_active == True,
                t2.is_active == True,
                distance_exp < context.config.l2_memory_consolidation_distance_threshold,
            )
            .order_by(func.random())  # order by random to lessen chance of infinite loops
            .limit(limit)
        ),
        map(do(lambda row: logging.info(f"Found redundant pair: {row[0].id} and {row[1].id}. Distance = {row[2]}"))),
        map(lambda row: (row[0], row[1])),
    )  # type: ignore


def upsert_embedding(context: ElroyContext, row: EmbeddableSqlModel) -> None:
    from ..llm.client import get_embedding

    new_text = row.to_fact()
    new_md5 = hashlib.md5(new_text.encode()).hexdigest()

    # Check if vector storage exists for this row
    vector_storage = context.session.exec(
        select(VectorStorage).where(VectorStorage.source_type == row.__class__.__name__, VectorStorage.source_id == row.id)
    ).first()

    if vector_storage and vector_storage.embedding_text_md5 == new_md5:
        logging.info("Old and new text matches md5, skipping")
        return
    else:
        embedding = get_embedding(context.config.embedding_model, new_text)
        if vector_storage:
            vector_storage.embedding_data = embedding
            vector_storage.embedding_text_md5 = new_md5
        else:
            vector_storage = VectorStorage(
                source_type=row.__class__.__name__, source_id=row.id, embedding_data=embedding, embedding_text_md5=new_md5  # type: ignore
            )

        context.session.add(vector_storage)
        context.session.commit()
