import logging
import re
from typing import Iterable, List, Type

from ...core.constants import SYSTEM, tool
from ...core.ctx import ElroyContext
from ...core.tracing import tracer
from ...db.db_models import DocumentExcerpt, EmbeddableSqlModel, Goal, Memory
from ...llm.client import get_embedding, query_llm
from ..context_messages.data_models import ContextMessage
from ..context_messages.transforms import format_context_messages
from ..user.queries import get_assistant_name
from ..user.tools import get_user_preferred_name


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
def get_relevant_memories(ctx: ElroyContext, query: List[float]) -> List[Memory]:
    """Get the most relevant memory for the given query."""
    return list(query_vector(Memory, ctx, query))  # type: ignore


@tracer.chain
def get_relevant_goals(ctx: ElroyContext, query: List[float]) -> List[Goal]:
    return list(query_vector(Goal, ctx, query))  # type: ignore


@tracer.chain
def rerank_memories(
    ctx: ElroyContext,
    context_messages: List[ContextMessage],
    memories: List[EmbeddableSqlModel],
) -> List[EmbeddableSqlModel]:
    """Rerank memories based on the query."""

    if len(memories) <= 1:
        return memories

    prompt_list = [
        "# Conversation:\n"
        + format_context_messages(
            [m for m in context_messages if m.role != SYSTEM],
            get_user_preferred_name(ctx),
            get_assistant_name(ctx),
        ),
        "# Memories:",
    ]

    for idx, memory in enumerate(memories):
        prompt_list.append(f"## {idx}:\n##{memory.to_fact()}")

    response = query_llm(
        model=ctx.chat_model,
        prompt="\n\n".join(prompt_list),
        system=f"""You will be given a list of memories and a conversation transcript. Each memory will have an index starting with 0.
        Rank the memories according to relevance. Each line of your reply should start with the index of the memory, and a short rationale for why you've ranked the memory where you did.get_embedding(
        If a memory is irrelevant, include (Irrelevant) for that memory's line.

        Example input:

        # Conversation:
        USER: I'm going to Target to buy some household supplies
        ASSISTANT: What do you think you should get?
        USER: I think I need some paper towels and cleaning supplies.

        # Memories:
        ## 0:
        ### The baseball game
        I played a baseball game yestrday and I was the pitcher.

        ## 1:
        ### The gas station near target
        I filled up my car at the gas station near Target.

        ## 2:
        ### My preference in paper towels
        I prefer Bounty paper towels because they are more absorbent.


        Example response:
        2: The paper towels are relevant because the user is going to Target to buy household supplies.
        1: The gas station is relevant because the user is going to Target, and the gas station is nearby
        0: (Irrelevant) The baseball game is irrelevant because it doesn't relate to the user's trip to Target.
        """,
    )

    reranked_memories = []
    for line in response.split("\n"):
        if line.strip() == "":
            continue
        try:
            # regex to extract any characters that start the line and are numeric
            if "(irrelevant)" in line.lower():
                continue
            match = re.search(r"^\d+", line)
            if not match:
                continue
            idx = int(match.group(0))
            if idx < 0 or idx >= len(memories):
                logging.info("Index out of range for memory list: %s", idx)
                continue
            reranked_memories.append(memories[idx])
        except ValueError:
            continue
    return reranked_memories
