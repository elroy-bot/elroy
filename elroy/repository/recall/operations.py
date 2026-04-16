import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial

from sqlmodel import select
from toolz import pipe
from toolz.curried import filter

from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import EmbeddableSqlModel
from ...db.db_session import DbSession
from ...llm.client import LlmClient
from ..context_messages.data_models import ContextMessage
from ..memories.transforms import to_fast_recall_tool_call
from .queries import is_in_context, is_in_context_message

logger = get_logger()


@dataclass(frozen=True)
class RecallOperationCallbacks:
    get_context_messages_fn: Callable[[], Iterable[ContextMessage]]
    add_context_messages_fn: Callable[[Iterable[ContextMessage]], None]
    remove_context_messages_fn: Callable[[list[ContextMessage]], None]


class RecallOperationService:
    def __init__(self, db: DbSession, user_id: int, llm: "LlmClient", callbacks: RecallOperationCallbacks):
        self.db = db
        self.user_id = user_id
        self.llm = llm
        self.callbacks = callbacks

    def upsert_embedding_if_needed(self, row: EmbeddableSqlModel) -> None:
        new_text = row.to_fact()
        new_md5 = hashlib.md5(new_text.encode()).hexdigest()
        current_md5 = self.db.get_embedding_text_md5(row)

        if current_md5 == new_md5:
            logger.info("Old and new text matches md5, skipping")
            if row.is_active is not True:
                self.db.update_embedding_active(row)
            return

        embedding = self.llm.get_embedding(new_text)
        if current_md5 is not None:
            self.db.update_embedding(row, embedding, new_md5)
        else:
            self.db.insert_embedding(row=row, embedding_data=embedding, embedding_text_md5=new_md5)
        if row.is_active is not True:
            self.db.update_embedding_active(row)

    def add_to_context(self, memory: EmbeddableSqlModel) -> None:
        memory_id = memory.id
        assert memory_id

        context_messages = self.callbacks.get_context_messages_fn()
        if is_in_context(context_messages, memory):
            logger.info(f"Memory of type {memory.__class__.__name__} with id {memory_id} already in context.")
        else:
            self.callbacks.add_context_messages_fn(to_fast_recall_tool_call([memory]))

    def remove_from_context(self, memory: EmbeddableSqlModel) -> None:
        pipe(
            self.callbacks.get_context_messages_fn(),
            filter(partial(is_in_context_message, memory)),
            list,
            self.callbacks.remove_context_messages_fn,
        )

    def add_to_current_context_by_name(self, name: str, memory_type: type[EmbeddableSqlModel]) -> str:
        item = self.db.exec(select(memory_type).where(memory_type.name == name)).first()  # type: ignore

        if item:
            self.add_to_context(item)
            return f"{memory_type.__name__} '{name}' added to context."
        return f"{memory_type.__name__} '{name}' not found."

    def drop_from_context_by_name(self, name: str, memory_type: type[EmbeddableSqlModel]) -> str:
        item = self.db.exec(select(memory_type).where(memory_type.name == name)).first()  # type: ignore

        if item:
            self.remove_from_context(item)
            return f"{memory_type.__name__} '{name}' dropped from context."
        return f"{memory_type.__name__} '{name}' not found."


def _service(ctx: ElroyContext) -> RecallOperationService:
    from ..context_messages.operations import add_context_messages, remove_context_messages
    from ..context_messages.queries import get_context_messages

    return RecallOperationService(
        db=ctx.db,
        user_id=ctx.user_id,
        llm=ctx.llm,
        callbacks=RecallOperationCallbacks(
            get_context_messages_fn=lambda: get_context_messages(ctx),
            add_context_messages_fn=lambda messages: add_context_messages(ctx, messages),
            remove_context_messages_fn=lambda messages: remove_context_messages(ctx, messages),
        ),
    )


def upsert_embedding_if_needed(ctx: ElroyContext, row: EmbeddableSqlModel) -> None:
    _service(ctx).upsert_embedding_if_needed(row)


def add_to_context(ctx: ElroyContext, memory: EmbeddableSqlModel) -> None:
    _service(ctx).add_to_context(memory)


def remove_from_context(ctx: ElroyContext, memory: EmbeddableSqlModel):
    _service(ctx).remove_from_context(memory)


def add_to_current_context_by_name(ctx: ElroyContext, name: str, memory_type: type[EmbeddableSqlModel]) -> str:
    return _service(ctx).add_to_current_context_by_name(name, memory_type)


def drop_from_context_by_name(ctx: ElroyContext, name: str, memory_type: type[EmbeddableSqlModel]) -> str:
    return _service(ctx).drop_from_context_by_name(name, memory_type)
