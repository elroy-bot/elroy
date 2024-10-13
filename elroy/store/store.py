from typing import Iterable

from sqlmodel import Session, select

from elroy.store.data_models import ArchivalMemory


def get_archival_messages(session: Session, user_id: int) -> Iterable[ArchivalMemory]:
    return session.exec(select(ArchivalMemory).where(ArchivalMemory.user_id == user_id)).all()


def persist_archival_memory(session: Session, user_id: int, name: str, text: str) -> None:
    archival_memory = ArchivalMemory(user_id=user_id, name=name, text=text)
    session.add(archival_memory)
    session.commit()
    session.refresh(archival_memory)
    from elroy.store.embeddings import upsert_embedding

    archival_memory_id = archival_memory.id
    assert archival_memory_id

    upsert_embedding(session, archival_memory)
