from typing import List, Union

from elroy.repository.context_messages.data_models import ContextMessage

from ...db.db_models import EmbeddableSqlModel
from ...models import RecallMetadata, RecallResponse
from ..context_messages.tools import to_synthetic_tool_call


def to_fast_recall_tool_call(memories: Union[EmbeddableSqlModel, List[EmbeddableSqlModel]]) -> List[ContextMessage]:
    if isinstance(memories, EmbeddableSqlModel):
        memories = [memories]

    return to_synthetic_tool_call(
        func_name="get_fast_recall",
        func_response=RecallResponse(
            content="\n".join([m.to_fact() for m in memories]),
            recall_metadata=[RecallMetadata(memory_type=m.__class__.__name__, memory_id=m.id, name=m.get_name()) for m in memories],  # type: ignore
        ),  # type: ignore
    )
