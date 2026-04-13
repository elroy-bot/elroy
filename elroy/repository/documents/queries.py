from pathlib import Path

from ...core.ctx import ElroyContext
from ...core.services.document_service import DocumentQueryService
from ...db.db_models import DocumentExcerpt, SourceDocument


def _document_queries(ctx: ElroyContext) -> DocumentQueryService:
    return DocumentQueryService(ctx.db, ctx.user_id)


def get_source_docs(ctx: ElroyContext):
    return _document_queries(ctx).get_source_docs()


def get_source_doc_by_address(ctx: ElroyContext, address: Path | str) -> SourceDocument | None:
    return _document_queries(ctx).get_source_doc_by_address(address)


def get_source_doc_excerpts(ctx: ElroyContext, source_doc: SourceDocument) -> list[DocumentExcerpt]:
    return _document_queries(ctx).get_source_doc_excerpts(source_doc)


def get_source_doc_by_content_md5(ctx: ElroyContext, content_md5: str) -> SourceDocument | None:
    return _document_queries(ctx).get_source_doc_by_content_md5(content_md5)
