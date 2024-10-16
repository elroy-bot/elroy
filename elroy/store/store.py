from typing import Iterable

from sqlmodel import select

from elroy.config import ElroyContext
from elroy.store.data_models import ArchivalMemory


def get_archival_messages(context: ElroyContext) -> Iterable[ArchivalMemory]:
    return context.session.exec(select(ArchivalMemory).where(ArchivalMemory.user_id == context.user_id)).all()


def persist_archival_memory(context: ElroyContext, name: str, text: str) -> None:
    archival_memory = ArchivalMemory(user_id=context.user_id, name=name, text=text)
    context.session.add(archival_memory)
    context.session.commit()
    context.session.refresh(archival_memory)
    from elroy.store.embeddings import upsert_embedding

    archival_memory_id = archival_memory.id
    assert archival_memory_id

    upsert_embedding(context.session, archival_memory)
