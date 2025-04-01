import fnmatch
import hashlib
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, Iterator, List

from ...config.llm import ChatModel
from ...core.constants import RecoverableToolError, allow_unused
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...core.tracing import tracer
from ...db.db_models import DocumentExcerpt, SourceDocument
from ...llm.client import query_llm
from ...utils.clock import utc_now
from ..memories.operations import do_create_memory
from ..recall.operations import upsert_embedding_if_needed
from .queries import get_source_doc_by_address, get_source_doc_excerpts

logger = get_logger()


@dataclass
class DocumentChunk:
    address: str
    content: str
    chunk_index: int


@allow_unused
@tracer.chain
def convert_to_text(chat_model: ChatModel, content: str) -> str:
    return query_llm(
        system="Your task is to convert the following text into plain text. You should NOT summarize content, "
        "but rather convert it into plain text. That is, the information in the output should be the same as the information in the input.",
        model=chat_model,
        prompt=content,
    )


class DocIngestResult(Enum):
    SUCCESS = "Document has been ingested successfully."
    UPDATED = "Document has been re-ingested successfully."
    UNCHANGED = "Document not ingested as it has not changed."
    TOO_LONG = "Document exceeds the configured max_ingested_doc_lines, and was not ingested."
    FAILED = "Document ingestion failed."


def should_process_file(path: Path, include: List[str], exclude: List[str]) -> bool:
    """
    Determine if a file or directory should be processed based on include and exclude glob patterns.

    Args:
        path (Path): The path to the file or directory to check
        include (str, optional): Comma-separated glob patterns to include. If specified, path must match at least one pattern.
        exclude (list[str], optional): List of glob patterns to exclude. If specified, path must not match any pattern.

    Returns:
        bool: True if the path should be processed, False otherwise
    """
    path_str = str(path)

    # First check exclude patterns against full path
    if any(fnmatch.fnmatch(path_str, pattern) for pattern in exclude):
        return False

    # Then check include patterns against just filename if includes specified
    if include:
        return any(fnmatch.fnmatch(path.name, pattern) for pattern in include)

    return True


def recursive_file_walk(directory: Path, include: List[str], exclude: List[str]) -> Generator[Path, Any, None]:
    for root, dirnames, files in os.walk(directory):
        root_path = Path(root)

        dirnames[:] = [d for d in dirnames if not any(fnmatch.fnmatch(str(root_path / d / "**"), pattern) for pattern in exclude)]
        for file in files:
            file_path = Path(os.path.join(root, file))
            if should_process_file(file_path, include, exclude):
                yield file_path


def do_ingest_dir(
    ctx: ElroyContext,
    directory: Path,
    force_refresh: bool,
    recursive: bool,
    include: List[str],
    exclude: List[str],
) -> Dict[DocIngestResult, int]:
    """
    Recursively ingest all files in a directory that match the include/exclude patterns.

    Args:
        ctx (ElroyContext): The Elroy context
        directory (str): The directory to recursively ingest
        force_refresh (bool, optional): If True, will re-ingest documents even if they seem unchanged. Defaults to False.
        include (str, optional): Comma-separated glob patterns to include. If specified, files must match at least one pattern.
        exclude (list[str], optional): List of glob patterns to exclude. If specified, files and directories must not match any pattern.

    Returns:
        int: Number of files successfully processed
    """
    if not os.path.isdir(directory):
        raise RecoverableToolError(f"{directory} is not a directory.")

    if recursive:
        file_paths = recursive_file_walk(directory, include, exclude)
    else:
        file_paths = (Path(os.path.join(directory, f)) for f in os.listdir(directory) if should_process_file(Path(f), include, exclude))

    results = {}

    for file_path in file_paths:
        try:
            result = do_ingest(ctx, file_path, force_refresh)
            results[result] = results.get(result, 0) + 1
        except Exception as e:
            results[DocIngestResult.FAILED] = results.get(DocIngestResult.FAILED, 0) + 1
            logger.warning(f"Failed to ingest {file_path}: {str(e)}")

    return results


def do_ingest(ctx: ElroyContext, address: Path, force_refresh: bool) -> DocIngestResult:
    """Downloads the document at the given address, and extracts content into memory.

    Args:
        address (str): The address of the document. Can be a local file, or a url.
        force (bool, optional): If True, will re-ingest the document even if it has already been ingested and seems to be unchanged. Defaults to False.

    Returns:
        str: The content of the document.
    """
    if os.path.isdir(address):
        raise RecoverableToolError(f"{address} is a directory, please specify a file.")
    elif not os.path.isfile(address):
        raise RecoverableToolError(f"Invalid path: {address}")

    if not is_markdown(address):
        logger.info("non-markdown files may not have optimal results")

    if not os.path.isfile(address):
        raise NotImplementedError("Only local files are supported at the moment.")

    if os.path.isfile(address):
        if not Path(address).is_absolute():
            logger.info(f"Converting relative path {address} to absolute path.")
            address = address.resolve()

    with open(address, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if len(lines) > ctx.max_ingested_doc_lines:
        logger.info(f"Document {address} exceeds max_ingested_doc_lines ({ctx.max_ingested_doc_lines}), skipping")
        return DocIngestResult.TOO_LONG

    content = "\n".join(lines)

    source_doc = get_source_doc_by_address(ctx, address)

    content_md5 = hashlib.md5(content.encode()).hexdigest()

    doc_was_updated = False

    if source_doc:
        if source_doc.content_md5 != content_md5:
            logger.info("Source doc contents changed, re-ingesting")
        elif force_refresh:
            logger.info(f"Force flag set, re-ingesting doc {address}")
        else:
            logger.info(f"Source doc {address} not changed and no force flag set, skipping")
            return DocIngestResult.UNCHANGED
        logger.info(f"Refreshing source doc {address}")

        source_doc.content = content
        source_doc.extracted_at = utc_now()
        source_doc.content_md5 = content_md5
        mark_source_document_excerpts_inactive(ctx, source_doc)
        doc_was_updated = True

    else:
        logger.info(f"Persisting source document {address}")
        source_doc = SourceDocument(
            user_id=ctx.user_id,
            address=str(address),
            name=str(address),
            content=content,
            content_md5=content_md5,
            extracted_at=utc_now(),
        )

    ctx.db.add(source_doc)
    ctx.db.commit()
    ctx.db.refresh(source_doc)
    source_doc_id = source_doc.id
    assert source_doc_id

    logger.info(f"Breaking source document into chunks for storage: {address}")
    for chunk in excerpts_from_doc(address, content):
        title = f"Excerpt {chunk.chunk_index} from doc {address}"
        doc_excerpt = DocumentExcerpt(
            source_document_id=source_doc_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            is_active=True,
            user_id=ctx.user_id,
            name=title,
            content_md5=hashlib.md5(chunk.content.encode()).hexdigest(),
        )

        ctx.db.add(doc_excerpt)
        ctx.db.commit()
        ctx.db.refresh(doc_excerpt)
        upsert_embedding_if_needed(ctx, doc_excerpt)

        logger.info(f"Creating memory from excerpt of document {address} (chunk {chunk.chunk_index})")

        do_create_memory(
            ctx,
            title,
            chunk.content,
            [doc_excerpt],
            True,
        )
    return DocIngestResult.SUCCESS if not doc_was_updated else DocIngestResult.UPDATED


def excerpts_from_doc(address: Path, content: str) -> Generator[DocumentChunk, Any, None]:
    if is_markdown(address):
        yield from chunk_markdown(address, content)
    else:
        yield from chunk_generic(address, content)


def mark_source_document_excerpts_inactive(ctx: ElroyContext, source_document: SourceDocument) -> None:
    for excerpt in get_source_doc_excerpts(ctx, source_document):
        excerpt.is_active = None
        ctx.db.add(excerpt)
    ctx.db.commit()


def chunk_generic(address: Path, content: str, max_chars: int = 3000, overlap: int = 200) -> Iterator[DocumentChunk]:
    """Chunk any text file into overlapping segments of roughly max_chars length.

    Args:
        address: Source file path
        content: Text content to chunk
        max_chars: Target maximum characters per chunk
        overlap: Number of characters to overlap between chunks

    Returns:
        Iterator of DocumentChunk objects
    """

    logger.info(f"Chunking file: {address}: Generic file chunker, performance might be suboptimal.")

    # Split on paragraph breaks
    splits = re.split(r"(\n\s*\n)", content)

    last_emitted_chunk = None
    current_chunk = ""

    for split in splits:
        if len(current_chunk) + len(split) < max_chars:
            current_chunk += split
        else:
            if last_emitted_chunk and overlap:
                current_chunk = last_emitted_chunk.content[:-overlap] + current_chunk
            last_emitted_chunk = DocumentChunk(
                str(address),
                current_chunk,
                last_emitted_chunk.chunk_index + 1 if last_emitted_chunk else 0,
            )
            yield last_emitted_chunk
            current_chunk = ""

    if current_chunk:
        if last_emitted_chunk and overlap:
            current_chunk = last_emitted_chunk.content[-overlap:] + current_chunk
        yield DocumentChunk(
            str(address),
            current_chunk,
            last_emitted_chunk.chunk_index + 1 if last_emitted_chunk else 0,
        )


def chunk_markdown(address: Path, content: str, max_chars: int = 3000, overlap: int = 200) -> Iterator[DocumentChunk]:
    # Split on markdown headers or double newlines
    splits = re.split(r"(#{1,6}\s.*?\n|(?:\n\n))", content)

    last_emitted_chunk = None
    current_chunk = ""

    for split in splits:
        if len(current_chunk) + len(split) < max_chars:
            current_chunk += split
        else:
            if last_emitted_chunk and overlap:
                current_chunk = last_emitted_chunk.content[:-overlap] + current_chunk
            last_emitted_chunk = DocumentChunk(
                str(address),
                current_chunk,
                last_emitted_chunk.chunk_index + 1 if last_emitted_chunk else 0,
            )
            yield last_emitted_chunk
            current_chunk = ""
    if current_chunk and overlap and last_emitted_chunk:
        current_chunk = last_emitted_chunk.content[-overlap:] + current_chunk
    yield DocumentChunk(
        str(address),
        current_chunk,
        last_emitted_chunk.chunk_index + 1 if last_emitted_chunk else 0,
    )


def is_markdown(address: Path) -> bool:
    return str(address).endswith(".md") or str(address).endswith(".markdown")
