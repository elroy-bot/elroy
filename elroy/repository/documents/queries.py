from pathlib import Path

from ...core.services.document_service import DocumentQueryService
from ...db.db_models import DocumentExcerpt, SourceDocument
from ...db.db_session import DbSession


def document_query_service(db: DbSession, user_id: int) -> DocumentQueryService:
    return DocumentQueryService(db, user_id)


def get_source_docs(query_service: DocumentQueryService):
    return query_service.get_source_docs()


def get_source_doc_by_address(query_service: DocumentQueryService, address: Path | str) -> SourceDocument | None:
    return query_service.get_source_doc_by_address(address)


def get_source_doc_excerpts(query_service: DocumentQueryService, source_doc: SourceDocument) -> list[DocumentExcerpt]:
    return query_service.get_source_doc_excerpts(source_doc)


def get_source_doc_by_content_md5(query_service: DocumentQueryService, content_md5: str) -> SourceDocument | None:
    return query_service.get_source_doc_by_content_md5(content_md5)
