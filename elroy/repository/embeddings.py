import hashlib
import logging
from functools import partial
from typing import Iterable, List, Type

from toolz import compose

from ..config.config import ElroyContext
from ..db.db_models import EmbeddableSqlModel, Goal, Memory
from ..utils.utils import first_or_none


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

    return context.db.query_vector(
        context.config.l2_memory_relevance_distance_threshold,
        table,
        context.user_id,
        query,
    )


get_most_relevant_goal = compose(first_or_none, partial(query_vector, Goal))
get_most_relevant_memory = compose(first_or_none, partial(query_vector, Memory))


def upsert_embedding_if_needed(context: ElroyContext, row: EmbeddableSqlModel) -> None:
    from ..llm.client import get_embedding

    new_text = row.to_fact()
    new_md5 = hashlib.md5(new_text.encode()).hexdigest()

    # Check if vector storage exists for this row
    vector_storage_row = context.db.get_vector_storage_row(row)

    if vector_storage_row and vector_storage_row.embedding_text_md5 == new_md5:
        logging.info("Old and new text matches md5, skipping")
        return
    else:
        embedding = get_embedding(context.config.embedding_model, new_text)
        if vector_storage_row:
            context.db.update_embedding(vector_storage_row, embedding, new_md5)
        else:
            context.db.insert_embedding(row=row, embedding_data=embedding, embedding_text_md5=new_md5)
