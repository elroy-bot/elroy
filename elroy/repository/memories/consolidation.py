import logging
from dataclasses import dataclass
from functools import cached_property, partial
from typing import List

import numpy as np
from scipy.spatial.distance import cosine
from sklearn.cluster import DBSCAN
from toolz import pipe
from toolz.curried import map, take

from ...config.ctx import ElroyContext
from ...db.db_models import Memory
from ...llm.client import query_llm
from ...utils.utils import do_asyncio_run
from .prompts import MEMORY_CONSOLIDATION


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


def consolidate_memories(ctx: ElroyContext):
    """Consolidate memories by finding clusters of similar memories and consolidating them into a single memory."""
    from .queries import get_active_memories

    clusters = pipe(
        get_active_memories(ctx),
        partial(_find_clusters, ctx),
        take(3),
    )

    for cluster in clusters:
        assert isinstance(cluster, MemoryCluster)
        do_asyncio_run(consolidate_memory_cluster(ctx, cluster))


def _find_clusters(ctx: ElroyContext, memories: List[Memory]) -> List[MemoryCluster]:
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


def _create_consolidated_memory(ctx: ElroyContext, name: str, text: str, sources: List[Memory]):
    from .operations import do_create_memory, mark_inactive

    logging.info(f"Creating consolidated memory {name} for user {ctx.user_id}")

    memory = do_create_memory(ctx, name, text, sources)  # type: ignore

    [mark_inactive(ctx, m) for m in sources]
    assert isinstance(memory, Memory)
    memory_id = memory.id
    assert memory_id
    return memory_id


async def consolidate_memory_cluster(ctx: ElroyContext, cluster: MemoryCluster, raise_on_failure: bool = False):

    logging.info(f"Consolidating memories {len(cluster)} memories in cluster.")
    response = query_llm(
        system=MEMORY_CONSOLIDATION,
        prompt=str(cluster),
        model=ctx.chat_model,
    )

    new_ids = []

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

    current_title = ""
    current_content = []

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

                    new_id = _create_consolidated_memory(
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
            new_id = _create_consolidated_memory(
                ctx=ctx,
                name=current_title,
                text=content,
                sources=cluster.memories,
            )
            new_ids.append(new_id)
        except Exception as e:
            if raise_on_failure:
                raise
            else:
                logging.warning(f"Failed to create memory '{current_title}': {e}")

    if not new_ids:
        logging.info("No new memories were created from consolidation response. Original memories left unchanged.")
        logging.debug(f"Original response was: {response}")
