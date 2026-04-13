from pathlib import Path

from ...core.services.document_service import (
    DocIngestStatus,
    DocumentIngestService,
)
from ...db.db_session import DbSession


def document_ingest_service(
    db: DbSession,
    user_id: int,
    *,
    max_ingested_doc_lines: int,
    sync_embedding,
    create_memory_from_excerpt,
) -> DocumentIngestService:
    return DocumentIngestService(
        db,
        user_id,
        max_ingested_doc_lines=max_ingested_doc_lines,
        sync_embedding=sync_embedding,
        create_memory_from_excerpt=create_memory_from_excerpt,
    )


def do_ingest_dir(
    ingest_service: DocumentIngestService,
    directory: Path,
    force_refresh: bool,
    recursive: bool,
    include: list[str],
    exclude: list[str],
):
    return ingest_service.ingest_dir(directory, force_refresh, recursive, include, exclude)


def do_ingest(ingest_service: DocumentIngestService, address: Path, force_refresh: bool) -> DocIngestStatus:
    return ingest_service.ingest(address, force_refresh)


def mark_source_document_excerpts_inactive(ingest_service: DocumentIngestService, source_document) -> None:
    ingest_service.mark_source_document_excerpts_inactive(source_document)
