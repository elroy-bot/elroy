from collections.abc import Iterable
from typing import cast

from pydantic import BaseModel, Field
from toolz import concat, pipe, unique
from toolz.curried import map, remove, tail

from ...core.constants import SYSTEM, TOOL
from ...core.logging import get_logger, log_execution_time
from ...db.db_models import EmbeddableSqlModel, MemorySource
from ...llm.client import LlmClient
from ..context_messages.data_models import ContextMessage
from ..context_messages.tools import to_synthetic_tool_call
from ..context_messages.transforms import format_context_messages
from ..data_models import RecallMetadata, RecallResponse
from ..recall.queries import get_recall_metadata
from .transforms import to_fast_recall_tool_call

logger = get_logger()


class MemoryRecallBuilder:
    def get_message_content(self, context_messages: list[ContextMessage], n: int) -> str:
        return pipe(
            context_messages,
            remove(lambda x: x.role == SYSTEM),
            remove(lambda x: x.role == TOOL),
            tail(n),
            map(lambda x: f"{x.role}: {x.content}" if x.content else None),
            remove(lambda x: x is None),
            list,
            "\n".join,
        )

    def build_fast_recall(self, memories: Iterable[EmbeddableSqlModel]) -> list[ContextMessage]:
        memories_list = list(memories)
        if not memories_list:
            return []
        return to_fast_recall_tool_call(memories_list)

    @log_execution_time
    def build_reflective_recall(
        self,
        llm: LlmClient,
        context_messages: Iterable[ContextMessage],
        memories: Iterable[EmbeddableSqlModel],
        assistant_name: str,
        user_preferred_name: str | None,
    ) -> list[ContextMessage]:
        memories_list = list(memories)
        if not memories_list:
            return []

        class ReflectionResponse(BaseModel):
            content: str | None = Field(
                description="The content of the reflection on the memories, written in the first person. If memories are irrelevant, this field should be empty"
            )
            is_relevant: bool = Field(description="Whether or not any of the recalled information is relevant to the conversation.")

        output = pipe(
            memories_list,
            map(lambda x: x.to_fact()),
            "\n\n".join,
            lambda x: (
                "Recalled Memory Content\n\n"
                + x
                + "#Converstaion Transcript:\n"
                + format_context_messages(
                    tail(3, list(context_messages)[1:]),
                    user_preferred_name or "User",
                    assistant_name,
                )
            ),
            lambda x: llm.query_llm_with_response_format(
                x,
                """#Identity and Purpose

        I am the internal thoughts of an AI assistant. I am reflecting on memories that have entered my awareness.

        I am considering recalled context, as well as the transcript of a recent conversation. I am:
        - Re-stating the most relevant context from the recalled content
        - Reflecting on how the recalled content relates to the conversation transcript

        Specific examples are most helpful. For example, if the recalled content is:

        "USER mentioned that when playing basketball, they struggle to remember to follow through on their shots."

        and the conversation transcript includes:
        "USER: I'm going to play basketball next week"

        a good response would be:
        "I remember that USER struggles to remember to follow through on their shots when playing basketball. I should remind USER about following through on their shots for next week's game."


        My response will be in the first person, and will be transmitted to an AI assistant to inform their response. My response will NOT be transmitted to the user.

        My response is brief and to the point, no more than 100 words.
        """,
                response_format=ReflectionResponse,
            ),
        )

        assert isinstance(output, ReflectionResponse)
        if not output.is_relevant:
            return []
        if output.is_relevant and not output.content:
            logger.warning("Memories deemed relevant, but no content returned.")
            return []
        assert output.content
        return to_synthetic_tool_call(
            "get_reflective_recall",
            RecallResponse(content=output.content, recall_metadata=self._build_recall_metadata(cast(list[MemorySource], memories_list))),
        )

    def get_in_context_memories_metadata(self, context_messages: Iterable[ContextMessage]) -> list[str]:
        return pipe(
            context_messages,
            map(get_recall_metadata),
            concat,
            map(lambda m: f"{m.memory_type}: {m.name}"),
            unique,
            list,
            sorted,
        )

    def _build_recall_metadata(self, memories: list[MemorySource]) -> list[RecallMetadata]:
        recall_metadata: list[RecallMetadata] = []
        for memory in memories:
            memory_id = memory.id
            assert memory_id is not None
            recall_metadata.append(
                RecallMetadata(
                    memory_type=memory.__class__.__name__,
                    memory_id=memory_id,
                    name=memory.get_name(),
                )
            )
        return recall_metadata
