import time
from collections.abc import Iterable
from typing import Any, cast

from sqlmodel import select
from toolz import first

from ...core.ctx import ElroyContext
from ...db.db_models import ContextMessageSet
from .data_models import ContextMessage
from .transforms import ContextMessageSetWithMessages


def get_or_create_context_message_set(ctx: ElroyContext) -> ContextMessageSetWithMessages:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            db_entry = ctx.db.exec(
                select(ContextMessageSet).where(
                    ContextMessageSet.user_id == ctx.user_id,
                    cast(Any, ContextMessageSet.is_active),
                )
            ).first()
            if db_entry:
                return ContextMessageSetWithMessages.from_context_message_set(ctx.db.session, db_entry)

            db_entry = ContextMessageSet(user_id=ctx.user_id, message_ids="[]", is_active=True)
            ctx.db.add(db_entry)
            ctx.db.commit()
            ctx.db.refresh(db_entry)
            return ContextMessageSetWithMessages.from_context_message_set(ctx.db.session, db_entry)
        except Exception:
            ctx.db.rollback()
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1 * 2**attempt)

    raise RuntimeError("Failed to get or create context message set")


def get_context_messages(ctx: ElroyContext) -> Iterable[ContextMessage]:
    """
    Gets context messages from db, in order of their position in ContextMessageSet
    """

    yield from get_or_create_context_message_set(ctx).messages


def get_current_system_instruct(ctx: ElroyContext) -> ContextMessage | None:
    try:
        return first(get_context_messages(ctx))
    except StopIteration:
        return None
