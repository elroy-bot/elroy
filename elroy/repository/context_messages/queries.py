from typing import Iterable, Optional

from sqlmodel import select
from toolz import first

from ...core.ctx import ElroyContext
from ...db.db_models import ContextMessageSet
from .data_models import ContextMessage
from .transforms import ContextMessageSetWithMessages


def get_or_create_context_message_set(ctx: ElroyContext) -> ContextMessageSetWithMessages:
    db_entry = ctx.db.exec(
        select(ContextMessageSet).where(
            ContextMessageSet.user_id == ctx.user_id,
            ContextMessageSet.is_active == True,
        )
    ).first()
    if db_entry:
        return ContextMessageSetWithMessages.from_context_message_set(ctx.db.session, db_entry)
    else:
        db_entry = ContextMessageSet(user_id=ctx.user_id, message_ids="[]", is_active=True)
        ctx.db.add(db_entry)
        ctx.db.commit()
        ctx.db.refresh(db_entry)
        return ContextMessageSetWithMessages.from_context_message_set(ctx.db.session, db_entry)


def get_context_messages(ctx: ElroyContext) -> Iterable[ContextMessage]:
    """
    Gets context messages from db, in order of their position in ContextMessageSet
    """

    yield from get_or_create_context_message_set(ctx).messages


def get_current_system_instruct(ctx: ElroyContext) -> Optional[ContextMessage]:
    try:
        return first(get_context_messages(ctx))
    except StopIteration:
        return None
