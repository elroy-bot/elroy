import hashlib
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Iterator

from ...config.constants import RecoverableToolError, allow_unused
from ...config.ctx import ElroyContext
from ...config.llm import ChatModel
from ...db.db_models import DocumentExcerpt, SourceDocument
from ...llm.client import query_llm
from ...utils.clock import get_utc_now
from ..memories.operations import do_create_memory
from ..recall.operations import upsert_embedding_if_needed
from .queries import get_source_doc_by_address, get_source_doc_excerpts


@dataclass
class DocumentChunk:
    address: str
    content: str
    chunk_index: int


@allow_unused
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
    SKIPPED = "Document not ingested as it has not changed."
    TOO_LONG = "Document exceeds the configured max_ingested_doc_lines, and was not ingested."


def do_ingest_doc(ctx: ElroyContext, address: str, force_refresh: bool) -> DocIngestResult:
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
        logging.info("non-markdown files may not have optimal results")

    if not os.path.isfile(address):
        raise NotImplementedError("Only local files are supported at the moment.")

    if os.path.isfile(address):
        if not Path(address).is_absolute():
            logging.info(f"Converting relative path {address} to absolute path.")
            address = os.path.abspath(address)

    with open(address, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if len(lines) > ctx.max_ingested_doc_lines:
        logging.info(f"Document {address} exceeds max_ingested_doc_lines ({ctx.max_ingested_doc_lines}), skipping")
        return DocIngestResult.TOO_LONG

    content = "\n".join(lines)

    source_doc = get_source_doc_by_address(ctx, address)

    content_md5 = hashlib.md5(content.encode()).hexdigest()

    doc_was_updated = False

    if source_doc:
        if source_doc.content_md5 != content_md5:
            logging.info("Source doc contents changed, re-ingesting")
        elif force_refresh:
            logging.info(f"Force flag set, re-ingesting doc {address}")
        else:
            logging.info(f"Source doc {address} not changed and no force flag set, skipping")
            return DocIngestResult.SKIPPED
        logging.info(f"Refreshing source doc {address}")

        source_doc.content = content
        source_doc.extracted_at = get_utc_now()  # noqa F841
        source_doc.content_md5 = content_md5
        mark_source_document_excerpts_inactive(ctx, source_doc)
        doc_was_updated = True

    else:
        logging.info(f"Persisting source document {address}")
        source_doc = SourceDocument(
            user_id=ctx.user_id,
            address=address,
            name=address,
            content=content,
            content_md5=content_md5,
            extracted_at=get_utc_now(),
        )

    ctx.db.add(source_doc)
    ctx.db.commit()
    ctx.db.refresh(source_doc)
    source_doc_id = source_doc.id
    assert source_doc_id

    logging.info(f"Breaking source document into chunks for storage: {address}")
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

        logging.info(f"Creating memory from excerpt of document {address} (chunk {chunk.chunk_index})")

        do_create_memory(
            ctx,
            title,
            chunk.content,
            [doc_excerpt],
            True,
            False,
        )
    return DocIngestResult.SUCCESS if not doc_was_updated else DocIngestResult.UPDATED


def excerpts_from_doc(address: str, content: str) -> Generator[DocumentChunk, Any, None]:
    if is_markdown(address):
        yield from chunk_markdown(address, content)
    else:
        yield from chunk_generic(address, content)


def mark_source_document_excerpts_inactive(ctx: ElroyContext, source_document: SourceDocument) -> None:
    for excerpt in get_source_doc_excerpts(ctx, source_document):
        excerpt.is_active = None
        ctx.db.add(excerpt)
    ctx.db.commit()


def chunk_generic(address: str, content: str, max_chars: int = 3000, overlap: int = 200) -> Iterator[DocumentChunk]:
    """Chunk any text file into overlapping segments of roughly max_chars length.

    Args:
        address: Source file path
        content: Text content to chunk
        max_chars: Target maximum characters per chunk
        overlap: Number of characters to overlap between chunks

    Returns:
        Iterator of DocumentChunk objects
    """

    logging.info(f"Chunking file: {address}: Generic file chunker, performance might be suboptimal.")

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
                address,
                current_chunk,
                last_emitted_chunk.chunk_index + 1 if last_emitted_chunk else 0,
            )
            yield last_emitted_chunk
            current_chunk = ""

    if current_chunk:
        if last_emitted_chunk and overlap:
            current_chunk = last_emitted_chunk.content[-overlap:] + current_chunk
        yield DocumentChunk(
            address,
            current_chunk,
            last_emitted_chunk.chunk_index + 1 if last_emitted_chunk else 0,
        )


def chunk_markdown(address: str, content: str, max_chars: int = 3000, overlap: int = 200) -> Iterator[DocumentChunk]:
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
                address,
                current_chunk,
                last_emitted_chunk.chunk_index + 1 if last_emitted_chunk else 0,
            )
            yield last_emitted_chunk
            current_chunk = ""
    if current_chunk and overlap and last_emitted_chunk:
        current_chunk = last_emitted_chunk.content[-overlap:] + current_chunk
    yield DocumentChunk(
        address,
        current_chunk,
        last_emitted_chunk.chunk_index + 1 if last_emitted_chunk else 0,
    )


def is_markdown(address: str) -> bool:
    return address.endswith(".md") or address.endswith(".markdown")
