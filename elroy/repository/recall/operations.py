import hashlib
from functools import partial
from typing import Type

from sqlmodel import select
from toolz import pipe
from toolz.curried import filter

from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import EmbeddableSqlModel
from ...llm.client import get_embedding
from ..context_messages.operations import add_context_messages, remove_context_messages
from ..context_messages.queries import get_context_messages
from ..memories.transforms import to_fast_recall_tool_call
from .queries import is_in_context, is_in_context_message

logger = get_logger()


def upsert_embedding_if_needed(ctx: ElroyContext, row: EmbeddableSqlModel) -> None:

    new_text = row.to_fact()
    new_md5 = hashlib.md5(new_text.encode()).hexdigest()

    # Check if vector storage exists for this row
    vector_storage_row = ctx.db.get_vector_storage_row(row)

    if vector_storage_row and vector_storage_row.embedding_text_md5 == new_md5:
        logger.info("Old and new text matches md5, skipping")
        return
    else:
        embedding = get_embedding(ctx.embedding_model, new_text)
        if vector_storage_row:
            ctx.db.update_embedding(vector_storage_row, embedding, new_md5)
        else:
            ctx.db.insert_embedding(row=row, embedding_data=embedding, embedding_text_md5=new_md5)


def add_to_context(ctx: ElroyContext, memory: EmbeddableSqlModel) -> None:

    memory_id = memory.id
    assert memory_id

    context_messages = get_context_messages(ctx)

    if is_in_context(context_messages, memory):
        logger.info(f"Memory of type {memory.__class__.__name__} with id {memory_id} already in context.")
    else:
        add_context_messages(ctx, to_fast_recall_tool_call([memory]))


def remove_from_context(ctx: ElroyContext, memory: EmbeddableSqlModel):

    pipe(
        get_context_messages(ctx),
        filter(partial(is_in_context_message, memory)),
        list,
        partial(remove_context_messages, ctx),
    )


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
