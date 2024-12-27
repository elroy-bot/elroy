import logging
from typing import List, Optional, Tuple

from sqlmodel import select

from ..config.config import ChatModel
from ..config.constants import MEMORY_WORD_COUNT_LIMIT
from ..config.ctx import ElroyContext
from ..db.db_models import Memory
from ..llm.client import query_llm
from .data_models import ContextMessage

MAX_MEMORY_LENGTH = 12000  # Characters


def manually_record_user_memory(ctx: ElroyContext, text: str, name: Optional[str] = None) -> None:
    """Manually record a memory for the user.

    Args:
        context (ElroyContext): The context of the user.
        name (str): The name of the memory. Should be specific and discuss one topic.
        text (str): The text of the memory.
    """

    if not text:
        raise ValueError("Memory text cannot be empty.")

    if len(text) > MAX_MEMORY_LENGTH:
        raise ValueError(f"Memory text exceeds maximum length of {MAX_MEMORY_LENGTH} characters.")

    if not name:
        name = query_llm(
            ctx.chat_model,
            system="Given text representing a memory, your task is to come up with a short title for a memory. "
            "If the title mentions dates, it should be specific dates rather than relative ones.",
            prompt=text,
        )

    create_memory(ctx, name, text)


async def formulate_memory(
    chat_model: ChatModel, user_preferred_name: Optional[str], context_messages: List[ContextMessage]
) -> Tuple[str, str]:
    from ..llm.prompts import summarize_for_memory
    from ..messaging.context import format_context_messages

    return await summarize_for_memory(
        chat_model,
        format_context_messages(context_messages, user_preferred_name),
        user_preferred_name,
    )


async def consolidate_memories(ctx: ElroyContext, memory1: Memory, memory2: Memory):

    if memory1.text == memory2.text:
        logging.info(f"Memories are identical, marking memory with id {memory2.id} as inactive.")
        memory2.is_active = False
        ctx.db.add(memory2)
        ctx.db.commit()
    else:

        ctx.io.internal_thought_msg(f"Consolidating memories '{memory1.name}' and '{memory2.name}'")
        response = query_llm(
            system=f"""# Memory Consolidation Task

Your task is to consolidate or reorganize two or more memory excerpts. These excerpts have been flagged as having overlapping or redundant content and require consolidation or reorganization.

Each excerpt has the following characteristics:
- They are written from the first-person perspective of an AI assistant.
- They consist of a title and a main body.

If the excerpts cover the same topic, consolidate them into a single, cohesive memory. If they address distinct topics, create separate, reorganized memories for each.

## Style Guidelines

- Limit each new memory excerpt to {MEMORY_WORD_COUNT_LIMIT} words.
- Use ISO 8601 format for dates and times to ensure references remain unambiguous in future retrievals.

## Memory Title Guidelines

Examples of effective and ineffective memory titles are provided:

**Ineffective:**
- UserFoo's project progress and personal goals: 'Personal goals' is too vague; two topics are referenced.

**Effective:**
- UserFoo's project on building a treehouse: Specific and topic-focused.
- UserFoo's goal to be more thoughtful in conversation: Specifies a clear goal.

**Ineffective:**
- UserFoo's weekend plans: 'Weekend plans' lacks specificity, and dates should be in ISO 8601 format.

**Effective:**
- UserFoo's plan to attend a concert on 2022-02-11: Specific with a defined date.

**Ineffective:**
- UserFoo's preferred name and well-being: Covers two distinct topics; 'well-being' is generic.

**Effective:**
- UserFoo's preferred name: Focused on a single topic.
- UserFoo's feeling of rejuvenation after rest: Clarifies the topic.

## Formatting

Responses should be in Markdown format, adhering strictly to these guidelines:

```markdown
# Memory Consolidation Reasoning
Provide a clear explanation of the consolidation or reorganization choices. Justify which information was included or omitted, and detail organizational strategies and considerations.

## Memory Title 1
Include all pertinent content from the original memories for the specified topic. Optionally, add reflections on how the assistant should respond to this information, along with any open questions the memory poses.

## Memory Title 2  (If necessary)
Detail the content for a second memory, should distinct topics require individual consolidation. Repeat as needed.
```

## Examples

Here are examples of effective consolidation:

### Input:
```markdown
# Memory Consolidation Input
## UserFoo's exercise progress for 2024-01-04
UserFoo felt tired but completed a 5-mile run. Encourage recognition of this achievement.

## UserFoo's workout for 2024-01-04
UserFoo did a long run as marathon prep. Encourage consistency!
```

### Output:
```markdown
# Memory Consolidation Reasoning
I combined the two memories, as they both describe the same workout and recommend similar interactions. I included specific marathon prep details to maintain context.

## UserFoo's exercise progress for 2024-01-04
Despite tiredness, UserFoo completed a 5-mile marathon prep run. I should consider inquiring about the marathon date and continue to offer encouragement.
```

### Input:
```markdown
# Memory Consolidation Input
## UserFoo's reading list update for 2024-02-15
UserFoo added several books to their reading list, including "The Pragmatic Programmer" and "Clean Code". I should track which ones they finish to offer recommendations.

## UserFoo's book recommendations from colleagues
UserFoo received recommendations from colleagues, specifically "The Pragmatic Programmer" and "Code Complete". They seemed interested in starting with these.
```

### Output:
```markdown
# Memory Consolidation Reasoning
I merged the two memories because they both pertain to UserFoo's interest in expanding their reading list with programming books. I prioritized the mention of recommendations from colleagues, as it might influence UserFoo's reading behavior.

## UserFoo's updated reading list as of 2024-02-15
UserFoo expanded their reading list, adding "The Pragmatic Programmer" and "Clean Code". Colleagues recommended "The Pragmatic Programmer" and "Code Complete", sparking UserFoo's interest in starting with the recommended titles. I should note when UserFoo completes a book to provide further recommendations.
```

### Input:
```markdown
# Memory Consolidation Input
## UserFoo's preferred programming languages
UserFoo enjoys working with Python and JavaScript. They mentioned an interest in exploring new frameworks in these languages.

## UserFoo's project interests
UserFoo is interested in developing a web application using Python. They are also keen on contributing to an open-source JavaScript library.
```

### Output:
```markdown
# Memory Consolidation Reasoning
I reorganized the memories since both touch on UserFoo's preferred programming languages and their project interests. Given the overlap in topics, separate memories were created to better capture their preferences and ongoing endeavors clearly.

## UserFoo's preferred programming languages
UserFoo enjoys programming with Python and JavaScript. They are interested in exploring new frameworks within these languages to advance their skills and projects.

## UserFoo's current project interests
Currently, UserFoo is focused on developing a web application using Python while also expressing a desire to contribute to an open-source JavaScript library. These projects reflect their interest in leveraging their preferred languages in practical contexts.
```
""",
            prompt="\n".join(
                [
                    "# Memory Consolidation Input",
                    f"## {memory1.name}",
                    f"{memory1.text}",
                    "\n",
                    f"## {memory2.name}",
                    f"{memory2.text}",
                ],
            ),
            model=ctx.chat_model,
        )

        new_ids = []
        current_title = ""
        current_content = []
        reasoning = None

        new_memory_parsing_line_start = 0
        lines = response.split("\n")
        for i, line in enumerate(lines):
            if line.lstrip().startswith("#"):
                first_header = line.strip()
                # Check if it looks like a reasoning section
                if "reason" in first_header.lower() or "consolidat" in first_header.lower():
                    # Find next header
                    next_header_idx = None
                    for j in range(i + 1, len(lines)):
                        if lines[j].lstrip().startswith("#"):
                            next_header_idx = j
                            break

                    if next_header_idx is None:
                        # No more headers - reasoning goes to end
                        logging.error("No content found after reasoning section, aborting memory consolidation")
                        return

                    else:
                        reasoning = "\n".join(lines[i:next_header_idx]).strip()
                        logging.info(f"Reasoning behind consolidation decisions: {reasoning}")
                        new_memory_parsing_line_start = next_header_idx
                        break
        if not reasoning:
            logging.error("No reasoning section found in consolidation response, interpreting all sections as memories")

        for line in lines[new_memory_parsing_line_start:]:
            line = line.strip()
            if not line:
                continue
            # Look for anything that could be a title (lines starting with # or ##)
            if line.startswith("#"):
                # If we have accumulated content, save it as a memory
                if current_title and current_content:
                    content = "\n".join(current_content).strip()
                    try:
                        new_id = create_memory(ctx, current_title, content)
                        new_ids.append(new_id)
                    except Exception as e:
                        logging.warning(f"Failed to create memory '{current_title}': {e}")
                current_title = line.lstrip("#").strip()
                current_content = []
            else:
                if not current_title:
                    logging.warning(f"Found content without a title: {line}, making the first line as memory title")
                    current_title = line
                current_content.append(line)

        if current_title and current_content:
            content = "\n".join(current_content).strip()
            try:
                new_id = create_memory(ctx, current_title, content)
                new_ids.append(new_id)
            except Exception as e:
                logging.warning(f"Failed to create memory '{current_title}': {e}")

        if new_ids:
            logging.info(f"Created {len(new_ids)} new memories with ids: {new_ids}")
            # Only mark old memories inactive if we successfully created new ones
            logging.info(f"Marking memories with ids {memory1.id} and {memory2.id} as inactive.")
            mark_memory_inactive(ctx, memory1)
            mark_memory_inactive(ctx, memory2)
        else:
            logging.warning("No new memories were created from consolidation response. Original memories left unchanged.")
            logging.debug(f"Original response was: {response}")


def mark_memory_inactive(ctx: ElroyContext, memory: Memory):
    from ..messaging.context import remove_from_context

    memory.is_active = False
    ctx.db.add(memory)
    ctx.db.commit()
    remove_from_context(ctx, memory)


def create_memory(ctx: ElroyContext, name: str, text: str) -> int:
    """Creates a new memory for the assistant.

    Examples of good and bad memory titles are below. Note, the BETTER examples, some titles have been split into two.:

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
        context (ElroyContext): _description_
        name (str): The name of the memory. Should be specific and discuss one topic.
        text (str): The text of the memory.

    Returns:
        int: The database ID of the memory.
    """
    from ..messaging.context import add_to_context

    memory = Memory(user_id=ctx.user_id, name=name, text=text)
    ctx.db.add(memory)
    ctx.db.commit()
    ctx.db.refresh(memory)
    from ..repository.embeddings import upsert_embedding_if_needed

    memory_id = memory.id
    assert memory_id

    upsert_embedding_if_needed(ctx, memory)
    add_to_context(ctx, memory)

    return memory_id


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
