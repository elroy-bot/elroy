from datetime import date, datetime

from ...db.db_models import AgendaItem
from ..recall.operations import RecallContextBridge, RecallIndexer
from .operations import TaskStore


class TaskMutationOrchestrator:
    def __init__(self, store: TaskStore, recall_indexer: RecallIndexer, recall_context_bridge: RecallContextBridge):
        self.store = store
        self.recall_indexer = recall_indexer
        self.recall_context_bridge = recall_context_bridge

    def _reindex_task(self, task: AgendaItem) -> AgendaItem:
        self.recall_indexer.upsert_embedding_if_needed(task)
        return task

    def _remove_task_from_context(self, task: AgendaItem) -> None:
        self.recall_context_bridge.remove_from_context(task)
        self.recall_indexer.upsert_embedding_if_needed(task)

    def create_task(
        self,
        name: str,
        text: str,
        *,
        item_date: date | None = None,
        trigger_datetime: datetime | None = None,
        trigger_context: str | None = None,
        allow_past_trigger: bool = False,
    ) -> AgendaItem:
        return self._reindex_task(
            self.store.create_task(
                name,
                text,
                item_date=item_date,
                trigger_datetime=trigger_datetime,
                trigger_context=trigger_context,
                allow_past_trigger=allow_past_trigger,
            )
        )

    def complete_task(self, task_name: str, closing_comment: str | None = None) -> AgendaItem:
        return self._reindex_task(self.store.complete_task(task_name, closing_comment))

    def delete_task(self, task_name: str, closing_comment: str | None = None, *, delete_file: bool = False) -> AgendaItem:
        task = self.store.delete_task(task_name, closing_comment, delete_file=delete_file)
        self._remove_task_from_context(task)
        return task

    def rename_task(self, old_name: str, new_name: str) -> AgendaItem:
        return self._reindex_task(self.store.rename_task(old_name, new_name))

    def update_task_text(self, task_name: str, new_text: str) -> AgendaItem:
        return self._reindex_task(self.store.update_task_text(task_name, new_text))
