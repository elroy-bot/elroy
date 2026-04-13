from pathlib import Path

from ...core.ctx import ElroyContext
from ...core.services.document_service import (
    DocIngestStatus,
    DocumentIngestService,
)
from ..memories.operations import do_create_memory
from ..recall.operations import upsert_embedding_if_needed


def _document_ingest_service(ctx: ElroyContext) -> DocumentIngestService:
    return DocumentIngestService(
        ctx.db,
        ctx.user_id,
        max_ingested_doc_lines=ctx.max_ingested_doc_lines,
        sync_embedding=lambda excerpt: upsert_embedding_if_needed(ctx, excerpt),
        create_memory_from_excerpt=lambda title, content, excerpts: do_create_memory(ctx, title, content, excerpts, False),
    )


def do_ingest_dir(
    ctx: ElroyContext,
    directory: Path,
    force_refresh: bool,
    recursive: bool,
    include: list[str],
    exclude: list[str],
):
    return _document_ingest_service(ctx).ingest_dir(directory, force_refresh, recursive, include, exclude)


def do_ingest(ctx: ElroyContext, address: Path, force_refresh: bool) -> DocIngestStatus:
    return _document_ingest_service(ctx).ingest(address, force_refresh)


def mark_source_document_excerpts_inactive(ctx: ElroyContext, source_document) -> None:
    _document_ingest_service(ctx).mark_source_document_excerpts_inactive(source_document)
