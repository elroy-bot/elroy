from typing import Iterable, List, Type, TypeVar

from ...core.constants import tool
from ...core.ctx import ElroyContext
from ...core.logging import log_execution_time
from ...core.tracing import tracer
from ...db.db_models import DocumentExcerpt, EmbeddableSqlModel, Goal, Memory, Reminder
from ...llm.client import get_embedding
from ..context_messages.data_models import ContextMessage


def is_in_context_message(memory: EmbeddableSqlModel, context_message: ContextMessage) -> bool:
    if not context_message.memory_metadata:
        return False
    return any(x.memory_type == memory.__class__.__name__ and x.id == memory.id for x in context_message.memory_metadata)


def is_in_context(context_messages: Iterable[ContextMessage], memory: EmbeddableSqlModel) -> bool:
    return any(is_in_context_message(memory, x) for x in context_messages)


T = TypeVar("T", bound=EmbeddableSqlModel)


@tracer.chain
def query_vector(
    table: Type[T],
    ctx: ElroyContext,
    query: List[float],
) -> Iterable[T]:
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
    )  # type: ignore


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
@log_execution_time
def get_most_relevant_memories(ctx: ElroyContext, query: List[float]) -> List[Memory]:
    """Get the most relevant memory for the given query."""
    return list(query_vector(Memory, ctx, query))[:2]


@tracer.chain
@log_execution_time
def get_most_relevant_goals(ctx: ElroyContext, query: List[float]) -> List[Goal]:
    return list(query_vector(Goal, ctx, query))[:2]


@tracer.chain
@log_execution_time
def get_most_relevant_reminders(ctx: ElroyContext, query: List[float]) -> List[Reminder]:
    return list(query_vector(Reminder, ctx, query))[:2]
