from ...db.db_models import EmbeddableSqlModel
from ..context_messages.data_models import RecalledMemoryMetadata


def to_recalled_memory_metadata(row: EmbeddableSqlModel) -> RecalledMemoryMetadata:
    assert row.id
    return RecalledMemoryMetadata(
        memory_type=row.__class__.__name__,
        id=row.id,
        name=row.get_name(),
    )
