from dataclasses import dataclass
from typing import Any, Dict, Union

from ...db.db_models import ContextMessageSet, Goal, Memory

EMBEDDABLE_TYPES = [Goal, Memory]
Embeddable = Union[*EMBEDDABLE_TYPES]


@dataclass
class RecalledMemoryMetadata:
    memory_type: str
    id: int
    name: str

    def to_json(self) -> Dict[str, Any]:
        return {"memory_type": self.memory_type, "id": self.id, "name": self.name}


def to_memory_metadata(row: Embeddable) -> RecalledMemoryMetadata:
    assert row.id
    return RecalledMemoryMetadata(memory_type=row.__class__.__name__, id=row.id, name=row.get_name())


MEMORY_SOURCE_TYPES = [Goal, Memory, ContextMessageSet]
MemorySource = Union[*MEMORY_SOURCE_TYPES]


def to_memory_source_d(row: MemorySource) -> Dict[str, Any]:
    return {"source_type": row.__class__.__name__, "id": row.id}
