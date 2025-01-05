import asyncio
import logging
from dataclasses import dataclass
from functools import cached_property, partial, wraps
from typing import Any, Callable, List

import numpy as np
from scipy.spatial.distance import cosine
from sklearn.cluster import DBSCAN
from sqlmodel import select
from toolz import pipe
from toolz.curried import map, take

from ...config.constants import MEMORY_WORD_COUNT_LIMIT
from ...config.ctx import ElroyContext
from ...db.db_models import Memory, MemoryOperationTracker
from ...llm.client import query_llm
from ...utils.utils import run_in_background_thread


@dataclass
class MemoryCluster:
    memories: List[Memory]
    embeddings: np.ndarray

    def __len__(self):
        return len(self.memories)

    def __str__(self) -> str:
        # Return a string representation of the object
        return pipe(
            self.memories,
            map(lambda x: "\n".join(["## Memory Title:", x.name, x.text])),
            list,
            "\n".join,
            lambda x: "#Memory Cluster:\n" + x,
        )  # type: ignore

    def __lt__(self, other: "MemoryCluster") -> bool:
        """Define default sorting behavior.
        First sort by cluster size (larger clusters first)
        Then by mean distance (tighter clusters first)"""

        return self._sort_key < other._sort_key

    @property
    def _sort_key(self):
        # Sort such that clusters early in a list are those that are most in need of consolidation.
        # Sort by: cluster size and then mean distance (ie tightness of cluster)
        return (-len(self), self.mean_distance)

    def token_count(self, chat_model_name: str):
        from litellm.utils import token_counter

        return token_counter(chat_model_name, text=str(self))

    @cached_property
    def distance_matrix(self) -> np.ndarray:
        """Lazily compute and cache the distance matrix."""
        size = len(self)
        _distance_matrix = np.zeros((size, size))
        for i in range(size):
            for j in range(i + 1, size):
                dist = cosine(self.embeddings[i], self.embeddings[j])
                _distance_matrix[i, j] = dist
                _distance_matrix[j, i] = dist
        return _distance_matrix

    @cached_property
    def mean_distance(self) -> float:
        """Calculate the mean intra cluster distance between all pairs of embeddings in the cluster using cosine similarity"""
        if len(self) < 2:
            return 0.0

        dist_matrix = self.distance_matrix
        # Get upper triangle of matrix (excluding diagonal of zeros)
        upper_triangle = dist_matrix[np.triu_indices_from(dist_matrix, k=1)]
        return float(np.mean(upper_triangle))

    def get_densest_n(self, n: int = 2) -> "MemoryCluster":
        """Get a new MemoryCluster containing the n members with lowest mean distance to other cluster members.

        Args:
            n: Number of members to return. Defaults to 2.

        Returns:
            A new MemoryCluster containing the n members with lowest mean distance to other members.
        """
        if len(self) <= n:
            return self

        dist_matrix = self.distance_matrix
        # Calculate mean distance for each member (excluding self-distance on diagonal)
        mean_distances = []
        for i in range(len(self)):
            # Get all distances except the diagonal (which is 0)
            member_distances = np.concatenate([dist_matrix[i, :i], dist_matrix[i, i + 1 :]])
            mean_dist = np.mean(member_distances)
            mean_distances.append((mean_dist, i))

        # Sort by mean distance and take top n indices
        mean_distances.sort(key=lambda x: x[0])
        closest_indices = [idx for _, idx in mean_distances[:n]]

        # Create new cluster with selected memories and embeddings
        return MemoryCluster(memories=[self.memories[i] for i in closest_indices], embeddings=self.embeddings[closest_indices])


def find_clusters(ctx: ElroyContext, memories: List[Memory]) -> List[MemoryCluster]:
    embeddings = []
    valid_memories = []
    for memory in memories:
        embedding = ctx.db.get_embedding(memory)
        if embedding is not None:
            embeddings.append(embedding)
            valid_memories.append(memory)

    if not embeddings:
        raise ValueError("No embeddings found for memories")

    embeddings_array = np.array(embeddings)

    # Perform DBSCAN clustering
    clustering = DBSCAN(
        eps=ctx.memory_cluster_similarity_threshold,
        metric="cosine",
        min_samples=ctx.min_memory_cluster_size,
    ).fit(embeddings_array)

    # Group memories by cluster
    clusters = {}
    for idx, label in enumerate(clustering.labels_):
        if label == -1:  # Skip noise points
            continue
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(idx)

    # Create MemoryCluster objects
    clusters = pipe(
        [
            MemoryCluster(
                embeddings=embeddings_array[indices],
                memories=[valid_memories[i] for i in indices],
            )
            for indices in clusters.values()
        ],
        map(lambda x: x.get_densest_n(ctx.max_memory_cluster_size)),
        list,
        partial(sorted),
    )

    return clusters


def consolidate_memories(ctx: ElroyContext):
    from .operations import get_active_memories

    clusters = pipe(
        get_active_memories(ctx),
        partial(find_clusters, ctx),
        take(3),
    )

    for cluster in clusters:
        assert isinstance(cluster, MemoryCluster)
        asyncio.run(consolidate_memory_cluster(ctx, cluster))


async def consolidate_memory_cluster(ctx: ElroyContext, cluster: MemoryCluster):

    ctx.io.internal_thought_msg(f"Consolidating memories {len(cluster)} memories in cluster.")
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
        prompt=str(cluster),
        model=ctx.chat_model,
    )

    from .operations import create_consolidated_memory

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

                    new_id = create_consolidated_memory(
                        ctx=ctx,
                        name=current_title,
                        text=content,
                        sources=cluster.memories,
                    )
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
            logging.info("Creating consolidated memory")
            create_consolidated_memory(
                ctx=ctx,
                name=current_title,
                text=content,
                sources=cluster.memories,
            )
        except Exception as e:
            logging.warning(f"Failed to create memory '{current_title}': {e}")

    if not new_ids:
        logging.warning("No new memories were created from consolidation response. Original memories left unchanged.")
        logging.debug(f"Original response was: {response}")


def memory_consolidation_check(func) -> Callable[..., Any]:
    @wraps(func)  # Add this line
    def wrapper(ctx: ElroyContext, *args, **kwargs):
        result = func(ctx, *args, **kwargs)

        logging.info("Checking memory consolidation")

        tracker = get_or_create_memory_op_tracker(ctx)

        tracker.memories_since_consolidation += 1
        logging.info(f"{tracker.memories_since_consolidation} memories since last consolidation")

        if tracker.memories_since_consolidation >= ctx.memories_between_consolidation:
            # Run consolidate_memories in a background thread
            logging.info("Running memory consolidation")
            run_in_background_thread(consolidate_memories, ctx)
            logging.info("Memory consolidation started in background thread")
            tracker.memories_since_consolidation = 0
        else:
            logging.info("Not running memory consolidation")
        ctx.db.add(tracker)
        ctx.db.commit()
        return result

    return wrapper


def get_or_create_memory_op_tracker(ctx: ElroyContext) -> MemoryOperationTracker:
    tracker = ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == ctx.user_id)).one_or_none()

    if tracker:
        return tracker
    else:
        # Create a new tracker for the user if it doesn't exist
        tracker = MemoryOperationTracker(user_id=ctx.user_id, memories_since_consolidation=0)
        return tracker
