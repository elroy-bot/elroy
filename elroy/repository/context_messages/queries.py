import time
from collections.abc import Iterable
from typing import Any, cast

from sqlmodel import select
from toolz import first

from ...core.ctx import ElroyConfig
from ...core.session import run_with_turn
from ...core.turn import TurnContext
from ...db.db_models import ContextMessageSet
from ...db.db_session import DbSession
from .data_models import ContextMessage
from .session import build_context_message_session
from .transforms import ContextMessageSetWithMessages


class ContextMessageReadStore:
    def __init__(self, db: DbSession, user_id: int):
        self.db = db
        self.user_id = user_id

    def get_or_create_context_message_set(self) -> ContextMessageSetWithMessages:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                db_entry = self.db.exec(
                    select(ContextMessageSet).where(
                        ContextMessageSet.user_id == self.user_id,
                        cast(Any, ContextMessageSet.is_active),
                    )
                ).first()
                if db_entry:
                    return ContextMessageSetWithMessages.from_context_message_set(self.db.session, db_entry)

                db_entry = ContextMessageSet(user_id=self.user_id, message_ids="[]", is_active=True)
                self.db.add(db_entry)
                self.db.commit()
                self.db.refresh(db_entry)
                return ContextMessageSetWithMessages.from_context_message_set(self.db.session, db_entry)
            except Exception:
                self.db.rollback()
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.1 * 2**attempt)

        raise RuntimeError("Failed to get or create context message set")

    def get_context_messages(self) -> Iterable[ContextMessage]:
        yield from self.get_or_create_context_message_set().messages

    def get_current_system_instruct(self) -> ContextMessage | None:
        try:
            return first(self.get_context_messages())
        except StopIteration:
            return None


def get_or_create_context_message_set(db: DbSession, user_id: int) -> ContextMessageSetWithMessages:
    return ContextMessageReadStore(db, user_id).get_or_create_context_message_set()


def do_get_context_messages(turn: TurnContext) -> Iterable[ContextMessage]:
    context_session = build_context_message_session(turn)
    return list(ContextMessageReadStore(context_session.db, context_session.user_id).get_context_messages())


def do_get_current_system_instruct(turn: TurnContext) -> ContextMessage | None:
    context_session = build_context_message_session(turn)
    return ContextMessageReadStore(context_session.db, context_session.user_id).get_current_system_instruct()


def get_context_messages(ctx: ElroyConfig) -> Iterable[ContextMessage]:
    return run_with_turn(ctx, do_get_context_messages)


def get_current_system_instruct(ctx: ElroyConfig) -> ContextMessage | None:
    return run_with_turn(ctx, do_get_current_system_instruct)
