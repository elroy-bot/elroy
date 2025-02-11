import json
from typing import Iterable, List, Optional

from sqlmodel import select
from toolz import first, pipe
from toolz.curried import map, pipe

from ...config.ctx import ElroyContext
from ...db.db_models import ContextMessageSet, Message
from .data_models import ContextMessage
from .transforms import db_message_to_context_message


def get_or_create_context_message_set(ctx: ElroyContext) -> ContextMessageSet:
    message_set = get_current_context_message_set_db(ctx)

    if message_set:
        return message_set

    message_set = ContextMessageSet(user_id=ctx.user_id, message_ids="[]", is_active=True)
    ctx.db.add(message_set)
    ctx.db.commit()

    return message_set


def get_current_context_message_set_db(ctx: ElroyContext) -> Optional[ContextMessageSet]:
    return ctx.db.exec(
        select(ContextMessageSet).where(
            ContextMessageSet.user_id == ctx.user_id,
            ContextMessageSet.is_active == True,
        )
    ).first()


def _get_context_messages_iter(ctx: ElroyContext) -> Iterable[ContextMessage]:
    """
    Gets context messages from db, in order of their position in ContextMessageSet
    """

    message_ids = pipe(
        get_current_context_message_set_db(ctx),
        lambda x: x.message_ids if x else "[]",
        json.loads,
    )

    assert isinstance(message_ids, list)

    return pipe(
        ctx.db.exec(select(Message).where(Message.id.in_(message_ids))),  # type: ignore
        lambda messages: sorted(messages, key=lambda m: message_ids.index(m.id)),
        map(db_message_to_context_message),
    )  # type: ignore


def get_context_messages(ctx: ElroyContext) -> List[ContextMessage]:
    return list(_get_context_messages_iter(ctx))


def get_current_system_message(ctx: ElroyContext) -> Optional[ContextMessage]:
    try:
        return first(_get_context_messages_iter(ctx))
    except StopIteration:
        return None
