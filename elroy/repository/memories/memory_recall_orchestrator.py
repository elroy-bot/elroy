from functools import partial

from toolz import concat, pipe
from toolz.curried import filter, remove

from ...core.configs import MemoryConfig
from ...db.db_models import AgendaItem, Memory
from ...db.db_session import DbSession
from ...llm.client import LlmClient
from ..context_messages.data_models import ContextMessage
from ..recall.queries import is_in_context
from .memory_recall_builder import MemoryRecallBuilder


class MemoryRecallOrchestrator:
    def __init__(
        self,
        db: DbSession,
        user_id: int,
        memory_config: MemoryConfig,
        llm: LlmClient,
        reflect: bool,
        recall_builder: MemoryRecallBuilder,
    ):
        self.db = db
        self.user_id = user_id
        self.memory_config = memory_config
        self.llm = llm
        self.reflect = reflect
        self.recall_builder = recall_builder

    def get_relevant_memories_and_due_items(self, query: str) -> list[Memory | AgendaItem]:
        query_embedding = self.llm.get_embedding(query)

        relevant_memories = [
            memory
            for memory in self.db.query_vector(
                self.memory_config.l2_memory_relevance_distance_threshold,
                Memory,
                self.user_id,
                query_embedding,
            )
            if isinstance(memory, Memory)
        ]

        relevant_due_items = [
            item
            for item in self.db.query_vector(
                self.memory_config.l2_memory_relevance_distance_threshold,
                AgendaItem,
                self.user_id,
                query_embedding,
            )
            if isinstance(item, AgendaItem) and (item.trigger_datetime or item.trigger_context)
        ][:2]

        return relevant_memories + relevant_due_items

    def get_relevant_memory_context_msgs(
        self,
        context_messages: list[ContextMessage],
        assistant_name: str,
        user_preferred_name: str | None,
    ) -> list[ContextMessage]:
        message_content = self.recall_builder.get_message_content(context_messages, 6)

        if not message_content:
            return []

        relevant_items = pipe(
            message_content,
            self.llm.get_embedding,
            lambda x: concat(
                [
                    self._get_most_relevant_memories(x),
                    self._get_most_relevant_due_items(x),
                    self._get_most_relevant_agenda_items(x),
                ]
            ),
            filter(lambda x: x is not None),
            remove(partial(is_in_context, context_messages)),
            list,
        )

        if self.reflect:
            return self.recall_builder.build_reflective_recall(
                self.llm,
                context_messages,
                relevant_items,
                assistant_name,
                user_preferred_name,
            )
        return self.recall_builder.build_fast_recall(relevant_items)

    def _get_most_relevant_memories(self, query: list[float]) -> list[Memory]:
        return [
            item
            for item in self.db.query_vector(self.memory_config.l2_memory_relevance_distance_threshold, Memory, self.user_id, query)
            if isinstance(item, Memory)
        ][:2]

    def _get_most_relevant_due_items(self, query: list[float]) -> list[AgendaItem]:
        return [
            item
            for item in self.db.query_vector(self.memory_config.l2_memory_relevance_distance_threshold, AgendaItem, self.user_id, query)
            if isinstance(item, AgendaItem) and (item.trigger_datetime or item.trigger_context)
        ][:2]

    def _get_most_relevant_agenda_items(self, query: list[float]) -> list[AgendaItem]:
        return [
            item
            for item in self.db.query_vector(self.memory_config.l2_memory_relevance_distance_threshold, AgendaItem, self.user_id, query)
            if isinstance(item, AgendaItem) and not (item.trigger_datetime or item.trigger_context)
        ][:2]
