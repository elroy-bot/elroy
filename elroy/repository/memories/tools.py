from typing import List, Optional, Tuple, Union

from rich.table import Table
from sqlmodel import desc, select
from toolz import pipe
from toolz.curried import map

from ...core.constants import RecoverableToolError, tool, user_only_tool
from ...core.ctx import ElroyContext
from ...db.db_models import Goal, Memory
from ...utils.clock import db_time_to_local
from .operations import do_create_memory, do_create_memory_from_ctx_msgs
from .queries import (
    db_get_memory_source_by_name,
    db_get_source_list_for_memory,
    get_memory_by_name,
    get_relevant_memories_and_goals,
)


def get_source_list_for_memory(ctx: ElroyContext, memory_name: str) -> List[Tuple[str, str]]:
    """Get a list of the sources of a memory by its name. This can be useful for retrieving more precise information that a memory is based on.

    Once the source is retrieved, the content of the source can be retrieved using the get_source_content tool.

    Args:
        memory_name (str): Name of the memory to retrieve the source for

    Returns:
        str: The source information for the memory, in the form {type}: {name}
    """

    memory = get_memory_by_name(ctx, memory_name)

    if not memory:
        raise RecoverableToolError(f"Memory '{memory_name}' not found for the current user.")
    else:
        sources = db_get_source_list_for_memory(ctx, memory)

        if not sources:
            return []
        else:
            return pipe(
                sources,
                map(lambda x: (x.source_type(), x.get_name())),
                list,
            )  # type: ignore


@tool
def get_source_content_for_memory(ctx: ElroyContext, memory_name: str, index: int = 0) -> str:
    """Retrieves content of the source for a memory, by source type and name.

    For a given memory, there can be multiple sources.

    Args:
        memory_name (str): Type of the source
        index (int): 0-indexed index of which source to retrieve.
    """

    metadata: List[Tuple[str, str]] = get_source_list_for_memory(ctx, memory_name)

    if not metadata:
        return f"No sources found for memory '{memory_name}'"

    if index >= len(metadata):
        raise RecoverableToolError(f"Index {index} out of range. Available indices: {list(range(len(metadata)))}")

    else:
        source_type, source_name = metadata[index]
        src = db_get_memory_source_by_name(ctx, source_type, source_name)

        if not src:
            return f"Source not found with type: {source_type}, name: {source_name}"
        else:
            return f"# Source content for memory: {memory_name} ({index} / {len(metadata) - 1})\n\n" + src.to_fact()


@tool
def examine_memories(ctx: ElroyContext, question: str) -> List[str]:
    """Search through memories for the answer to a question.

    This function searches summarized memories and goals. Each memory also contains source information.

    If a retrieved memory is relevant but lacks detail to answer the question, use the get_source_content_for_memory tool. This can be useful in cases where broad information about a topic is provided, but more exact recollection is necessary.

    Args:
        question (str): Question to examine memories for. Should be a full sentence, with any relevant context that might make the query more specific.

    Returns:
        str: A list of relevant memories and goals, formatted for the LLM.
    """

    recalled_items = get_relevant_memories_and_goals(ctx, question)
    relevant_memories = [item for item in recalled_items if isinstance(item, Memory)]
    relevant_goals = [item for item in recalled_items if isinstance(item, Goal)]

    # Format context for LLM
    output = []
    if relevant_memories:
        for memory in relevant_memories:
            output.append(
                f"""
# Memory: {memory.name}

*to view the source content this memory is based on, call tool `{get_source_content_for_memory.__name__}({memory.name}, idx)`

{memory.text}"""
            )

    if relevant_goals:
        for goal in relevant_goals:
            output.append(goal.to_fact())

    return output


@tool
def print_memory(ctx: ElroyContext, memory_name: str) -> str:
    """Retrieve and return a memory by its exact name.

    Args:
        memory_name (str): Name of the memory to retrieve

    Returns:
        str: The memory's content if found, or an error message if not found
    """
    memory = get_memory_by_name(ctx, memory_name)
    if memory:
        return memory.to_fact()
    else:
        return f"Memory '{memory_name}' not found for the current user."


@user_only_tool
def print_memories(ctx: ElroyContext, n: Optional[int] = None) -> Union[Table, str]:
    """Print all memories.

    Returns:
        str: A formatted string containing all memories.
    """
    memories = ctx.db.exec(
        select(Memory)
        .where(Memory.user_id == ctx.user_id, Memory.is_active == True)
        .order_by(desc(Memory.created_at))
        .limit(n if n else 1000)
    ).all()

    if not memories:
        return "No memories found."

    table = Table(title="Memories", show_lines=True)
    table.add_column("Name", style="cyan")
    table.add_column("Text", style="green")
    table.add_column("Created", style="magenta")

    for memory in reversed(memories):
        table.add_row(
            memory.name,
            memory.text,
            db_time_to_local(memory.created_at).strftime("%Y-%m-%d %H:%M:%S"),
        )

    return table


@user_only_tool
def search_memories(ctx: ElroyContext, query: str) -> Union[str, Table]:
    """Search for a memory by its text content.

    Args:
        query (str): Search query to find relevant memories

    Returns:
        str: A natural language response synthesizing relevant memories
    """

    items = get_relevant_memories_and_goals(ctx, query)

    if not items:
        return "No relevant memories found"

    table = Table(title="Search Results", show_lines=True)
    table.add_column("Type", style="cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Text", style="green")
    for item in items:
        table.add_row(item.__class__.__name__, item.name, item.to_fact())
    return table


@tool
def update_outdated_or_incorrect_memory(ctx: ElroyContext, memory_name: str, update_text: str) -> str:
    """Updates an existing memory with new information.
    In general, when new information arises, new memories should be created rather than updating.
    Reserve use of this tool for cases in which the information in a memory changes or becomes out of date.

    Args:
        memory_name (str): Name of the existing memory to update
        update_text (str): The new information to append to the memory

    Returns:
        str: Confirmation message that the memory was updated
    """
    original_memory = get_memory_by_name(ctx, memory_name)
    if not original_memory:
        return f"Memory '{memory_name}' not found"

    # Mark existing memory as inactive
    original_memory.is_active = False
    ctx.db.add(original_memory)

    # Create new memory with updated text
    update_time = db_time_to_local(original_memory.created_at).strftime("%Y-%m-%d %H:%M:%S")
    updated_text = f"{original_memory.text}\n\nUpdate ({update_time}):\n{update_text}"
    ctx.db.commit()

    do_create_memory(
        ctx,
        memory_name,
        updated_text,
        [original_memory],
        True,
    )

    return f"Memory '{memory_name}' has been updated"


@tool
def create_memory(ctx: ElroyContext, name: str, text: str) -> str:
    """Creates a new memory for the assistant.

    Examples of good and bad memory titles are below. Note that in the BETTER examples, some titles have been split into two:

    BAD:
    - [User Name]'s project progress and personal goals: 'Personal goals' is too vague, and the title describes two different topics.

    BETTER:
    - [User Name]'s project on building a treehouse: More specific, and describes a single topic.
    - [User Name]'s goal to be more thoughtful in conversation: Describes a specific goal.

    BAD:
    - [User Name]'s weekend plans: 'Weekend plans' is too vague, and dates must be referenced in ISO 8601 format.

    BETTER:
    - [User Name]'s plan to attend a concert on 2022-02-11: More specific, and includes a specific date.

    BAD:
    - [User Name]'s preferred name and well being: Two different topics, and 'well being' is too vague.

    BETTER:
    - [User Name]'s preferred name: Describes a specific topic.
    - [User Name]'s feeling of rejuvenation after rest: Describes a specific topic.

    Args:
        name (str): The name of the memory. Should be specific and discuss one topic.
        text (str): The text of the memory.

    Returns:
        str: Confirmation message that the memory was created.
    """

    do_create_memory_from_ctx_msgs(ctx, name, text)

    return f"New memory created: {name}"
