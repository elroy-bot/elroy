from typing import List, Tuple

from ..config.ctx import ElroyContext
from ..llm.client import get_embedding


def get_relevant_tools(ctx: ElroyContext, conversation_text: str) -> List[Tuple[str, float]]:
    """
    Get tools relevant to the current conversation context using embedding similarity.

    Args:
        ctx: The Elroy context
        conversation_text: Text from recent conversation to match against

    Returns:
        List of tuples containing (tool_name, similarity_score) sorted by relevance
    """

    # Generate embedding for conversation context
    query_embedding = get_embedding(ctx.embedding_model, conversation_text)

    # Get tool schemas from registry
    tool_schemas = ctx.tool_registry.get_schemas()

    # Convert schemas to searchable text
    tool_texts = []
    for schema in tool_schemas:
        name = schema["function"]["name"]
        desc = schema["function"]["description"]
        params = schema["function"]["parameters"]["properties"]

        # Format parameters and their descriptions
        param_text = "\n".join(f"- {param}: {details.get('description', '')}" for param, details in params.items())

        tool_texts.append(
            f"""Tool: {name}
Description: {desc}
Parameters:
{param_text}"""
        )

    # Generate embeddings for tool texts
    tool_embeddings = [get_embedding(ctx.embedding_model, text) for text in tool_texts]

    # Calculate similarities
    similarities = []
    for i, schema in enumerate(tool_schemas):
        tool_name = schema["function"]["name"]
        similarity = _calculate_cosine_similarity(query_embedding, tool_embeddings[i])
        similarities.append((tool_name, similarity))

    # Sort by similarity score
    return sorted(similarities, key=lambda x: x[1], reverse=True)


def _calculate_cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    import numpy as np

    v1_array = np.array(v1)
    v2_array = np.array(v2)
    return float(np.dot(v1_array, v2_array) / (np.linalg.norm(v1_array) * np.linalg.norm(v2_array)))
