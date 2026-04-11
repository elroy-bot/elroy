import time
from collections.abc import Iterable
from typing import Any, cast

from sqlmodel import select
from toolz import first

from ...core.ctx import ElroyContext
from ...db.db_models import ContextMessageSet
from ...db.db_session import DbSession
from .data_models import ContextMessage
from .transforms import ContextMessageSetWithMessages


def get_or_create_context_message_set(db: DbSession) -> ContextMessageSetWithMessages:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            db_entry = db.exec(
                select(ContextMessageSet).where(
                    cast(Any, ContextMessageSet.is_active),
                )
            ).first()
            if db_entry:
                return ContextMessageSetWithMessages.from_context_message_set(ctx.db.session, db_entry)

            db_entry = ContextMessageSet(message_ids="[]", is_active=True)
            db.add(db_entry)
            db.commit()
            db.refresh(db_entry)
            return ContextMessageSetWithMessages.from_context_message_set(ctx.db.session, db_entry)
        except Exception:
            db.rollback()
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1 * 2**attempt)

    raise RuntimeError("Failed to get or create context message set")


def get_context_messages(db: DbSession) -> Iterable[ContextMessage]:
    """
    Gets context messages from db, in order of their position in ContextMessageSet
    """

    yield from get_or_create_context_message_set(db).messages


def get_current_system_instruct(ctx: ElroyContext) -> ContextMessage | None:
    try:
        return first(get_context_messages(ctx))
    except StopIteration:
        return None
