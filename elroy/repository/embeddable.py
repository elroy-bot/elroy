from functools import partial
from typing import List, Type

from sqlmodel import select
from toolz import pipe
from toolz.curried import filter

from ..config.constants import SYSTEM
from ..config.ctx import ElroyContext
from ..db.db_models import EmbeddableSqlModel
from .data_models import ContextMessage
from .message import (
    MemoryMetadata,
    add_context_messages,
    get_context_messages,
    remove_context_messages,
)


def is_in_context_message(memory: EmbeddableSqlModel, context_message: ContextMessage) -> bool:
    if not context_message.memory_metadata:
        return False
    return any(x.memory_type == memory.__class__.__name__ and x.id == memory.id for x in context_message.memory_metadata)


def remove_from_context(ctx: ElroyContext, memory: EmbeddableSqlModel):
    pipe(
        get_context_messages(ctx),
        filter(partial(is_in_context_message, memory)),
        list,
        partial(remove_context_messages, ctx),
    )


def add_to_context(ctx: ElroyContext, memory: EmbeddableSqlModel) -> None:
    memory_id = memory.id
    assert memory_id

    add_context_messages(
        ctx,
        [
            ContextMessage(
                role=SYSTEM,
                memory_metadata=[MemoryMetadata(memory_type=memory.__class__.__name__, id=memory_id, name=memory.get_name())],
                content=memory.to_fact(),
                chat_model=None,
            )
        ],
    )


def is_in_context(context_messages: List[ContextMessage], memory: EmbeddableSqlModel) -> bool:
    return any(is_in_context_message(memory, x) for x in context_messages)


def add_to_current_context_by_name(ctx: ElroyContext, name: str, memory_type: Type[EmbeddableSqlModel]) -> str:
    item = ctx.db.exec(select(memory_type).where(memory_type.name == name)).first()  # type: ignore

    if item:
        add_to_context(ctx, item)
        return f"{memory_type.__name__} '{name}' added to context."
    else:
        return f"{memory_type.__name__} '{name}' not found."


def drop_from_context_by_name(ctx: ElroyContext, name: str, memory_type: Type[EmbeddableSqlModel]) -> str:
    item = ctx.db.exec(select(memory_type).where(memory_type.name == name)).first()  # type: ignore

    if item:
        remove_from_context(ctx, item)
        return f"{memory_type.__name__} '{name}' dropped from context."
    else:
        return f"{memory_type.__name__} '{name}' not found."
