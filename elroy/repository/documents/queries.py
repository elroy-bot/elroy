from pathlib import Path
from typing import Iterator, List, Optional, Union

from sqlmodel import select

from ...core.ctx import ElroyContext
from ...db.db_models import DocumentExcerpt, SourceDocument


def get_source_docs(ctx: ElroyContext) -> Iterator[SourceDocument]:
    return ctx.db.exec(select(SourceDocument).where(SourceDocument.user_id == ctx.user_id))


def get_source_doc_by_address(ctx: ElroyContext, address: Union[Path, str]) -> Optional[SourceDocument]:
    return ctx.db.exec(
        select(SourceDocument).where(
            SourceDocument.address == str(address),
            SourceDocument.user_id == ctx.user_id,
        )
    ).one_or_none()


def get_source_doc_excerpts(ctx: ElroyContext, source_doc: SourceDocument) -> List[DocumentExcerpt]:
    return list(
        ctx.db.exec(
            select(DocumentExcerpt).where(DocumentExcerpt.source_document_id == source_doc.id).where(DocumentExcerpt.is_active == True)
        ).all()
    )
