from typing import Iterable, List, Optional, Type

from ...core.constants import tool
from ...core.ctx import ElroyContext
from ...core.tracing import tracer
from ...db.db_models import DocumentExcerpt, EmbeddableSqlModel, Goal, Memory
from ...llm.client import get_embedding
from ...utils.utils import first_or_none
from ..context_messages.data_models import ContextMessage


def is_in_context_message(memory: EmbeddableSqlModel, context_message: ContextMessage) -> bool:
    if not context_message.memory_metadata:
        return False
    return any(x.memory_type == memory.__class__.__name__ and x.id == memory.id for x in context_message.memory_metadata)


def is_in_context(context_messages: Iterable[ContextMessage], memory: EmbeddableSqlModel) -> bool:
    return any(is_in_context_message(memory, x) for x in context_messages)


@tracer.chain
def query_vector(
    table: Type[EmbeddableSqlModel],
    ctx: ElroyContext,
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

    return list(
        ctx.db.query_vector(
            ctx.l2_memory_relevance_distance_threshold,
            table,
            ctx.user_id,
            query,
        )
    )


@tool
def search_documents(ctx: ElroyContext, query: str) -> str:
    """
    Search through document excerpts using semantic similarity.

    Args:
        query: The search query string

    Returns:
        str: A description of the found documents, or a message if none found
    """

    # Get embedding for the search query
    query_embedding = get_embedding(ctx.embedding_model, query)

    # Search for relevant documents using vector similarity
    results = query_vector(DocumentExcerpt, ctx, query_embedding)

    # Convert results to readable format
    found_docs = list(results)

    if not found_docs:
        return "No relevant documents found."

    # Format results into a response string
    response = "Found relevant document excerpts:\n\n"
    for doc in found_docs:
        response += f"- {doc.to_fact()}\n"

    return response


@tracer.chain
def get_most_relevant_memory(ctx: ElroyContext, query: List[float]) -> Optional[Memory]:
    """Get the most relevant memory for the given query."""
    mem = first_or_none(iter(query_vector(Memory, ctx, query)))

    if mem:
        assert isinstance(mem, Memory)
        return mem


@tracer.chain
def get_most_relevant_goal(ctx: ElroyContext, query: List[float]) -> Optional[Goal]:
    goal = first_or_none(iter(query_vector(Goal, ctx, query)))

    if goal:
        assert isinstance(goal, Goal)
        return goal
