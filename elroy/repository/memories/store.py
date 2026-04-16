import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import select

from ...db.db_models import EmbeddableSqlModel, Memory, MemoryOperationTracker, MemorySource
from ...db.db_session import DbSession


@dataclass(frozen=True)
class MemoryStoreConfig:
    memory_dir_path: Path


class MemoryStore:
    def __init__(self, db: DbSession, user_id: int, config: MemoryStoreConfig):
        self.db = db
        self.user_id = user_id
        self.config = config

    def get_or_create_memory_op_tracker(self) -> MemoryOperationTracker:
        tracker = self.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == self.user_id)).one_or_none()

        if tracker:
            return tracker
        return MemoryOperationTracker(user_id=self.user_id, memories_since_consolidation=0)

    def create_memory(self, name: str, text: str, source_metadata: Iterable[MemorySource]) -> Memory:
        from ..memories.file_storage import write_memory_file

        memory = self.db.persist(
            Memory(
                user_id=self.user_id,
                name=name,
                source_metadata=json.dumps([x.to_memory_source_d() for x in source_metadata]),
            )
        )

        assert memory.id is not None
        existing_paths: set[str] = {str(p) for p in self.config.memory_dir_path.glob("*.md")}
        file_path = write_memory_file(self.config.memory_dir_path, memory, text, existing_paths)
        memory.file_path = str(file_path)
        self.db.add(memory)
        self.db.commit()
        return memory

    def archive_memory_file_if_needed(self, item: EmbeddableSqlModel) -> None:
        if not isinstance(item, Memory) or not item.file_path:
            return

        from ..memories.file_storage import archive_memory_file

        file_path = Path(item.file_path)
        if file_path.exists():
            dest = archive_memory_file(file_path, self.config.memory_dir_path / "archive")
            item.file_path = str(dest)

    def mark_inactive(self, item: EmbeddableSqlModel) -> None:
        self.archive_memory_file_if_needed(item)
        item.is_active = False
        self.db.add(item)
        self.db.commit()
        self.db.update_embedding_active(item)
