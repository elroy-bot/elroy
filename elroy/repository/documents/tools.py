from ...config.constants import RecoverableToolError, tool
from ...config.ctx import ElroyContext
from .operations import DocIngestResult, do_ingest_doc
from .queries import get_source_doc_by_address, get_source_doc_excerpts, get_source_docs


@tool
def reingest_doc(ctx: ElroyContext, address: str) -> str:
    """Downloads the document at the given address, and extracts content into memory.

    Args:
        address (str): The address of the document. Can be a local file, or a url.

    Returns:
        str: The content of the document.
    """

    do_ingest_doc(ctx, address, True)
    return f"Document {address} has been re-ingested."


@tool
def get_source_documents(ctx: ElroyContext) -> str:
    """Gets the list of ingested source documents."""
    return "\n".join([doc.address for doc in get_source_docs(ctx)])


@tool
def get_source_doc_metadata(ctx: ElroyContext, address: str) -> str:
    """Gets metadata about a source document including extraction time and available chunks.

    Args:
        address: The address/path of the document

    Returns:
        str: A formatted string containing metadata about the document

    Raises:
        RecoverableToolError: If the document has not been ingested yet
    """
    source_doc = get_source_doc_by_address(ctx, address)
    if not source_doc:
        raise RecoverableToolError(f"Document at {address} has not been ingested yet. Use ingest_doc first.")

    excerpts = get_source_doc_excerpts(ctx, source_doc)
    active_excerpts = [e for e in excerpts if e.is_active]

    # Get available chunk indices
    chunk_indices = sorted([e.chunk_index for e in active_excerpts])

    metadata = [
        f"Document: {source_doc.name}",
        f"Extracted at: {source_doc.extracted_at}",
        f"Number of chunks: {len(active_excerpts)}",
        f"Available chunk indices: {chunk_indices}",
    ]

    return "\n".join(metadata)


@tool
def get_document_excerpt(ctx: ElroyContext, address: str, chunk_index: int) -> str:
    """Gets text of document excerpt by address and chunk index (0-indexed). Use get_source_doc_metadata to get available chunk indices.

    Args:
        address: The address/path of the document
        chunk_index: The 0-based index of the chunk to retrieve

    Returns:
        str: The content of the specified document chunk

    Raises:
        RecoverableToolError: If the document hasn't been ingested or the chunk index is invalid
    """
    source_doc = get_source_doc_by_address(ctx, address)
    if not source_doc:
        raise RecoverableToolError(f"Document at {address} has not been ingested yet. Use ingest_doc first.")

    excerpts = get_source_doc_excerpts(ctx, source_doc)
    active_excerpts = [e for e in excerpts if e.is_active]

    # Find the excerpt with matching chunk_index
    matching_excerpt = next((e for e in active_excerpts if e.chunk_index == chunk_index), None)

    if not matching_excerpt:
        available_indices = sorted([e.chunk_index for e in active_excerpts])
        raise RecoverableToolError(
            f"Chunk index {chunk_index} not found for document {address}. " f"Available chunk indices: {available_indices}"
        )

    return matching_excerpt.content


@tool
def ingest_doc(ctx: ElroyContext, address: str) -> str:
    """Downloads the document at the given address, and extracts content into memory.

    Args:
        address (str): The address of the document. Can be a local file, or a url.

    Returns:
        str: The content of the document.
    """

    result = do_ingest_doc(ctx, address, False)

    return f"Document {address} has been ingested." if DocIngestResult.SUCCESS == result else f"Document {address} has been updated."
