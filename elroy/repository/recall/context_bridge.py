from collections.abc import Callable, Iterable
from functools import partial

from sqlmodel import select
from toolz import pipe
from toolz.curried import filter

from ...core.logging import get_logger
from ...db.db_models import EmbeddableSqlModel
from ...db.db_session import DbSession
from ..context_messages.data_models import ContextMessage
from ..memories.transforms import to_fast_recall_tool_call
from .queries import is_in_context, is_in_context_message

logger = get_logger()


class RecallContextBridge:
    def __init__(
        self,
        db: DbSession,
        user_id: int,
        get_context_messages_fn: Callable[[], Iterable[ContextMessage]],
        add_context_messages_fn: Callable[[Iterable[ContextMessage]], None],
        remove_context_messages_fn: Callable[[list[ContextMessage]], None],
    ):
        self.db = db
        self.user_id = user_id
        self.get_context_messages_fn = get_context_messages_fn
        self.add_context_messages_fn = add_context_messages_fn
        self.remove_context_messages_fn = remove_context_messages_fn

    def add_to_context(self, memory: EmbeddableSqlModel) -> None:
        memory_id = memory.id
        assert memory_id

        context_messages = self.get_context_messages_fn()
        if is_in_context(context_messages, memory):
            logger.info(f"Memory of type {memory.__class__.__name__} with id {memory_id} already in context.")
        else:
            self.add_context_messages_fn(to_fast_recall_tool_call([memory]))

    def remove_from_context(self, memory: EmbeddableSqlModel) -> None:
        pipe(
            self.get_context_messages_fn(),
            filter(partial(is_in_context_message, memory)),
            list,
            self.remove_context_messages_fn,
        )

    def add_to_current_context_by_name(self, name: str, memory_type: type[EmbeddableSqlModel]) -> str:
        item = self.db.exec(select(memory_type).where(memory_type.name == name, memory_type.user_id == self.user_id)).first()  # type: ignore

        if item:
            self.add_to_context(item)
            return f"{memory_type.__name__} '{name}' added to context."
        return f"{memory_type.__name__} '{name}' not found."

    def drop_from_context_by_name(self, name: str, memory_type: type[EmbeddableSqlModel]) -> str:
        item = self.db.exec(select(memory_type).where(memory_type.name == name, memory_type.user_id == self.user_id)).first()  # type: ignore

        if item:
            self.remove_from_context(item)
            return f"{memory_type.__name__} '{name}' dropped from context."
        return f"{memory_type.__name__} '{name}' not found."
