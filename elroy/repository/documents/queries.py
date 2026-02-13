from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from sqlmodel import select

from ...core.ctx import ElroyContext
from ...db.db_models import DocumentExcerpt, SourceDocument


def get_source_docs(ctx: ElroyContext) -> Iterator[SourceDocument]:
    return ctx.db.exec(select(SourceDocument).where(SourceDocument.user_id == ctx.user_id))


def get_source_doc_by_address(ctx: ElroyContext, address: Path | str) -> SourceDocument | None:
    return ctx.db.exec(
        select(SourceDocument).where(
            SourceDocument.address == str(address),
            SourceDocument.user_id == ctx.user_id,
        )
    ).one_or_none()


def get_source_doc_excerpts(ctx: ElroyContext, source_doc: SourceDocument) -> list[DocumentExcerpt]:
    return list(
        ctx.db.exec(
            select(DocumentExcerpt).where(DocumentExcerpt.source_document_id == source_doc.id).where(cast(Any, DocumentExcerpt.is_active))
        ).all()
    )


def get_source_doc_by_content_md5(ctx: ElroyContext, content_md5: str) -> SourceDocument | None:
    """Find a source document with the same content MD5 hash, excluding the current address if provided."""
    return ctx.db.exec(
        select(SourceDocument).where(
            SourceDocument.content_md5 == content_md5,
            SourceDocument.user_id == ctx.user_id,
        )
    ).first()
