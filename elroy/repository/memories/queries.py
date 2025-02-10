from functools import partial
from typing import Iterable, List, Optional, Union

from rich.table import Table
from sqlmodel import select
from toolz import concat, juxt, pipe, unique
from toolz.curried import filter, map, remove, tail

from ...config.constants import SYSTEM, tool
from ...config.ctx import ElroyContext
from ...db.db_models import Goal, Memory, RecalledMemoryMetadata
from ...llm.client import get_embedding, query_llm
from ...utils.clock import db_time_to_local, get_utc_now
from ...utils.utils import logged_exec_time
from ..context_messages.data_models import ContextMessage
from ..embeddable import is_in_context
from ..embeddings import get_most_relevant_goal, get_most_relevant_memory


def get_active_memories(ctx: ElroyContext) -> List[Memory]:
    """Fetch all active memories for the user"""
    return list(
        ctx.db.exec(
            select(Memory).where(
                Memory.user_id == ctx.user_id,
                Memory.is_active == True,
            )
        ).all()
    )


def get_relevant_relevant_memories(ctx: ElroyContext, query: str) -> List[Union[Goal, Memory]]:
    query_embedding = get_embedding(ctx.embedding_model, query)

    relevant_memories = [
        memory
        for memory in ctx.db.query_vector(ctx.l2_memory_relevance_distance_threshold, Memory, ctx.user_id, query_embedding)
        if isinstance(memory, Memory)
    ]

    relevant_goals = [
        goal
        for goal in ctx.db.query_vector(ctx.l2_memory_relevance_distance_threshold, Goal, ctx.user_id, query_embedding)
        if isinstance(goal, Goal)
    ]

    return relevant_memories + relevant_goals


@tool
def examine_memories(ctx: ElroyContext, query: str) -> str:
    """Search through memories and goals using semantic search and return a synthesized response.

    Args:
        query (str): Search query to find relevant memories and goals

    Returns:
        str: A natural language response synthesizing relevant memories and goals
    """

    recalled_items = get_relevant_relevant_memories(ctx, query)
    relevant_memories = [item for item in recalled_items if isinstance(item, Memory)]
    relevant_goals = [item for item in recalled_items if isinstance(item, Goal)]

    # Format context for LLM
    context_parts = []
    if relevant_memories:
        context_parts.append("Relevant memories:")
        for memory in relevant_memories:
            context_parts.append(f"- {memory.name}: {memory.text}")

    if relevant_goals:
        if context_parts:
            context_parts.append("\n")
        context_parts.append("Relevant goals:")
        for goal in relevant_goals:
            context_parts.append(f"- {goal.name}: {goal.to_fact()}")

    if not context_parts:
        return "No relevant memories or goals found."

    context = "\n".join(context_parts)

    # Generate response using LLM
    system_prompt = """You are an AI assistant helping to answer questions based on retrieved memories and goals.
Your task is to analyze the provided context and answer the user's query thoughtfully.
Base your response entirely on the provided context. If the context doesn't contain relevant information, say so.
Answer the question directly, short and concise. Do not say things like "based on the current context", just answer straightforwardly.
"""

    return query_llm(
        model=ctx.chat_model,
        system=system_prompt,
        prompt=f"Query: {query}\n\nContext:\n{context}\n\nPlease provide a thoughtful response to the query based on the above context.",
    )


@tool
def print_memory(ctx: ElroyContext, memory_name: str) -> str:
    """Retrieve and return a memory by its exact name.

    Args:
        memory_name (str): Name of the memory to retrieve

    Returns:
        str: The memory's content if found, or an error message if not found
    """
    memory = ctx.db.exec(
        select(Memory).where(
            Memory.user_id == ctx.user_id,
            Memory.name == memory_name,
            Memory.is_active == True,
        )
    ).first()
    if memory:
        return memory.to_fact()
    else:
        return f"Memory '{memory_name}' not found for the current user."


@logged_exec_time
def get_relevant_memory_context_msgs(ctx: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    message_content = pipe(
        context_messages,
        remove(lambda x: x.role == SYSTEM),
        tail(4),
        map(lambda x: f"{x.role}: {x.content}" if x.content else None),
        remove(lambda x: x is None),
        list,
        "\n".join,
    )

    if not message_content:
        return []

    assert isinstance(message_content, str)

    new_memory_messages = pipe(
        message_content,
        partial(get_embedding, ctx.embedding_model),
        lambda x: juxt(get_most_relevant_goal, get_most_relevant_memory)(ctx, x),
        filter(lambda x: x is not None),
        remove(partial(is_in_context, context_messages)),
        map(
            lambda x: ContextMessage(
                role=SYSTEM,
                memory_metadata=[RecalledMemoryMetadata(memory_type=x.__class__.__name__, id=x.id, name=x.get_name())],
                content="Information recalled from assistant memory: " + x.to_fact(),
                chat_model=None,
            )
        ),
        list,
    )

    return new_memory_messages


def get_in_context_memories(ctx: ElroyContext, context_messages: Iterable[ContextMessage]) -> List[str]:
    return pipe(
        context_messages,
        filter(lambda m: not m.created_at or m.created_at > get_utc_now() - ctx.max_in_context_message_age),
        map(lambda m: m.memory_metadata),
        filter(lambda m: m is not None),
        concat,
        map(lambda m: f"{m.memory_type}: {m.name}"),
        unique,
        list,
        sorted,
    )  # type: ignore


def print_memories(ctx: ElroyContext, n: Optional[int] = None) -> Union[Table, str]:
    """Print all memories.

    Returns:
        str: A formatted string containing all memories.
    """
    memories = ctx.db.exec(
        select(Memory).where(Memory.user_id == ctx.user_id).order_by(Memory.created_at.desc()).limit(n if n else 1000)  # type: ignore
    ).all()

    if not memories:
        return "No memories found."

    table = Table(title="Memories", show_lines=True)
    table.add_column("Name", style="cyan")
    table.add_column("Text", style="green")
    table.add_column("Created", style="magenta")

    for memory in memories:
        table.add_row(
            memory.name,
            memory.text,
            db_time_to_local(memory.created_at).strftime("%Y-%m-%d %H:%M:%S"),
        )

    return table


def search_memories(ctx: ElroyContext, query: str) -> Union[str, Table]:
    """Search for a memory by its text content.

    Args:
        query (str): Search query to find relevant memories

    Returns:
        str: A natural language response synthesizing relevant memories
    """

    items = get_relevant_relevant_memories(ctx, query)

    if not items:
        return "No relevant memories found"

    table = Table(title="Search Results", show_lines=True)
    table.add_column("Type", style="cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Text", style="green")
    for item in items:
        table.add_row(item.__class__.__name__, item.name, item.to_fact())
    return table
