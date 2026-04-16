import fnmatch
import hashlib
import os
import re
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel
from sqlmodel import select

from ...core.constants import RecoverableToolError, allow_unused
from ...core.logging import get_logger
from ...db.db_models import DocumentExcerpt, SourceDocument
from ...db.db_session import DbSession
from ...llm.client import LlmClient
from ...utils.clock import utc_now

logger = get_logger()


@dataclass
class DocumentChunk:
    address: str
    content: str
    chunk_index: int


@allow_unused
def convert_to_text(llm: LlmClient, content: str) -> str:
    return llm.query_llm(
        system="Your task is to convert the following text into plain text. You should NOT summarize content, "
        "but rather convert it into plain text. That is, the information in the output should be the same as the information in the input.",
        prompt=content,
    )


class DocIngestStatus(Enum):
    SUCCESS = "Document has been ingested successfully."
    UPDATED = "Document has been re-ingested successfully."
    UNCHANGED = "Document not ingested as it has not changed."
    TOO_LONG = "Document exceeds the configured max_ingested_doc_lines, and was not ingested."
    PENDING = "Document is queued for ingestion"
    UNSUPPORTED_FORMAT = "Document format is not supported"
    MOVED = "Document existing document that had a different address, so existing doc address was updated."


class IngestDirStatusUpdate(BaseModel):
    total: int
    statuses: dict[DocIngestStatus, int]


class DocumentQueryService:
    def __init__(self, db: DbSession, user_id: int):
        self.db = db
        self.user_id = user_id

    def get_source_docs(self) -> Iterator[SourceDocument]:
        return self.db.exec(select(SourceDocument).where(SourceDocument.user_id == self.user_id))

    def get_source_doc_by_address(self, address: Path | str) -> SourceDocument | None:
        return self.db.exec(
            select(SourceDocument).where(
                SourceDocument.address == str(address),
                SourceDocument.user_id == self.user_id,
            )
        ).one_or_none()

    def get_source_doc_excerpts(self, source_doc: SourceDocument) -> list[DocumentExcerpt]:
        return list(
            self.db.exec(
                select(DocumentExcerpt)
                .where(DocumentExcerpt.source_document_id == source_doc.id)
                .where(cast(Any, DocumentExcerpt.is_active))
            ).all()
        )

    def get_source_doc_by_content_md5(self, content_md5: str) -> SourceDocument | None:
        return self.db.exec(
            select(SourceDocument).where(
                SourceDocument.content_md5 == content_md5,
                SourceDocument.user_id == self.user_id,
            )
        ).first()


class DocumentIngestService:
    def __init__(
        self,
        db: DbSession,
        user_id: int,
        *,
        max_ingested_doc_lines: int,
        sync_embedding: Callable[[DocumentExcerpt], None],
        create_memory_from_excerpt: Callable[[str, str, list[DocumentExcerpt]], None],
        query_service: DocumentQueryService | None = None,
    ):
        self.db = db
        self.user_id = user_id
        self.max_ingested_doc_lines = max_ingested_doc_lines
        self.sync_embedding = sync_embedding
        self.create_memory_from_excerpt = create_memory_from_excerpt
        self.query_service = query_service or DocumentQueryService(db, user_id)

    def ingest_dir(
        self,
        directory: Path,
        force_refresh: bool,
        recursive: bool,
        include: list[str],
        exclude: list[str],
    ) -> Generator[IngestDirStatusUpdate, None, None]:
        if not directory.is_dir():
            raise RecoverableToolError(f"{directory} is not a directory.")

        if recursive:
            file_paths = list(recursive_file_walk(directory, include, exclude))
        else:
            file_paths = [path for path in directory.iterdir() if should_process_file(path, include, exclude)]

        statuses = dict.fromkeys(DocIngestStatus, 0)
        yield IngestDirStatusUpdate(total=len(file_paths), statuses=statuses)

        for idx, file_path in enumerate(file_paths):
            try:
                result = self.ingest(file_path, force_refresh)
                statuses[result] = statuses.get(result, 0) + 1
            except Exception as e:
                logger.error(f"Failed to ingest {file_path}: {e!s}", exc_info=True)
                raise
            statuses[DocIngestStatus.PENDING] = len(file_paths) - (idx + 1)
            yield IngestDirStatusUpdate(total=len(file_paths), statuses=statuses)

        yield IngestDirStatusUpdate(total=len(file_paths), statuses=statuses)

    def ingest(self, address: Path, force_refresh: bool) -> DocIngestStatus:
        if address.is_dir():
            raise RecoverableToolError(f"{address} is a directory, please specify a file.")
        if not address.is_file():
            raise RecoverableToolError(f"Invalid path: {address}")

        if not is_markdown(address):
            logger.info("non-markdown files may not have optimal results")

        if address.is_file() and not address.is_absolute():
            logger.info(f"Converting relative path {address} to absolute path.")
            address = address.resolve()

        try:
            with address.open(encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            logger.warning(f"Cannot decode file {address} as utf-8, skipping")
            return DocIngestStatus.UNSUPPORTED_FORMAT

        if len(lines) > self.max_ingested_doc_lines:
            logger.info(f"Document {address} exceeds max_ingested_doc_lines ({self.max_ingested_doc_lines}), skipping")
            return DocIngestStatus.TOO_LONG

        content = "\n".join(lines)
        source_doc = self.query_service.get_source_doc_by_address(address)
        content_md5 = hashlib.md5(content.encode()).hexdigest()

        if source_doc:
            return self._refresh_existing_source_doc(source_doc, address, content, content_md5, force_refresh)

        source_doc, early_status = self._build_new_source_doc(address, content, content_md5)
        if early_status:
            return early_status

        self._persist_excerpts(source_doc, address, content)

        return DocIngestStatus.SUCCESS

    def _refresh_existing_source_doc(
        self,
        source_doc: SourceDocument,
        address: Path,
        content: str,
        content_md5: str,
        force_refresh: bool,
    ) -> DocIngestStatus:
        if source_doc.content_md5 != content_md5:
            logger.info("Source doc contents changed, re-ingesting")
        elif force_refresh:
            logger.info(f"Force flag set, re-ingesting doc {address}")
        else:
            logger.info(f"Source doc {address} not changed and no force flag set, skipping")
            return DocIngestStatus.UNCHANGED

        logger.info(f"Refreshing source doc {address}")
        source_doc.content = content
        source_doc.extracted_at = utc_now()
        source_doc.content_md5 = content_md5
        self.mark_source_document_excerpts_inactive(source_doc)
        self._persist_excerpts(source_doc, address, content)
        return DocIngestStatus.UPDATED

    def _build_new_source_doc(self, address: Path, content: str, content_md5: str) -> tuple[SourceDocument, DocIngestStatus | None]:
        existing_doc_with_same_content = self.query_service.get_source_doc_by_content_md5(content_md5)
        if existing_doc_with_same_content and existing_doc_with_same_content.address != str(address):
            logger.info(
                f"Found existing document with same content at {existing_doc_with_same_content.address}, updating address to {address}"
            )
            existing_doc_with_same_content.address = str(address)
            existing_doc_with_same_content.name = str(address)
            existing_doc_with_same_content.extracted_at = utc_now()
            self.db.persist(existing_doc_with_same_content)
            return existing_doc_with_same_content, DocIngestStatus.MOVED

        logger.info(f"Persisting source document {address}")
        return (
            SourceDocument(
                user_id=self.user_id,
                address=str(address),
                name=str(address),
                content=content,
                content_md5=content_md5,
                extracted_at=utc_now(),
            ),
            None,
        )

    def _persist_excerpts(self, source_doc: SourceDocument, address: Path, content: str) -> None:
        source_doc = self.db.persist(source_doc)
        source_doc_id = source_doc.id
        assert source_doc_id

        logger.info(f"Breaking source document into chunks for storage: {address}")
        for chunk in excerpts_from_doc(address, content):
            title = f"Excerpt {chunk.chunk_index} from doc {address}"
            doc_excerpt = self.db.persist(
                DocumentExcerpt(
                    source_document_id=source_doc_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    is_active=True,
                    user_id=self.user_id,
                    name=title,
                    content_md5=hashlib.md5(chunk.content.encode()).hexdigest(),
                )
            )

            self.sync_embedding(doc_excerpt)
            logger.info(f"Creating memory from excerpt of document {address} (chunk {chunk.chunk_index})")
            self.create_memory_from_excerpt(title, chunk.content, [doc_excerpt])

    def mark_source_document_excerpts_inactive(self, source_document: SourceDocument) -> None:
        for excerpt in self.query_service.get_source_doc_excerpts(source_document):
            excerpt.is_active = None
            self.db.add(excerpt)
        self.db.commit()


def should_process_file(path: Path, include: list[str], exclude: list[str]) -> bool:
    if path.name.startswith("."):
        return False

    path_str = str(path)
    if any(fnmatch.fnmatch(path_str, pattern) for pattern in exclude):
        return False
    if include:
        return any(fnmatch.fnmatch(path.name, pattern) for pattern in include)
    return True


def recursive_file_walk(directory: Path, include: list[str], exclude: list[str]) -> Generator[Path, Any, None]:
    for root, dirnames, files in os.walk(directory):
        root_path = Path(root)
        dirnames[:] = [
            d
            for d in dirnames
            if not d.startswith(".") and not any(fnmatch.fnmatch(str(root_path / d / "**"), pattern) for pattern in exclude)
        ]
        for file in files:
            file_path = Path(root) / file
            if should_process_file(file_path, include, exclude):
                yield file_path


def excerpts_from_doc(address: Path, content: str) -> Generator[DocumentChunk, Any, None]:
    if is_markdown(address):
        yield from chunk_markdown(address, content)
    else:
        yield from chunk_generic(address, content)


def chunk_generic(address: Path, content: str, max_chars: int = 3000, overlap: int = 200) -> Iterator[DocumentChunk]:
    if not str(address).endswith(".txt"):
        logger.info(f"Chunking file: {address}: Generic file chunker, performance might be suboptimal.")

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


def chunk_markdown(address: Path, content: str, max_tokens: int = 8000, overlap: int = 200) -> Iterator[DocumentChunk]:
    from litellm.utils import token_counter

    splits = re.split(r"(#{1,6}\s.*?\n|(?:\n\n))", content)
    last_emitted_chunk = None
    current_chunk = ""

    for split in splits:
        if token_counter(text=current_chunk) + token_counter(text=split) < max_tokens:
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
    return address.suffix.lower() in {".md", ".markdown", ".mdown", ".mkd"}
