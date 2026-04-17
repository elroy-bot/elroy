import json
import time
import traceback
from collections.abc import Callable, Iterable, Iterator
from functools import wraps
from typing import Any, TypeVar, cast

from sqlmodel import select

from ...core.logging import get_logger
from ...db.db_models import ContextMessageSet
from .data_models import ContextMessage
from .queries import ContextMessageReadStore
from .transforms import context_message_to_db_message

logger = get_logger()

T = TypeVar("T")


def retry_on_integrity_error[T](fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(self: "ContextMessageStore", *args: Any, **kwargs: Any) -> T:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return fn(self, *args, **kwargs)
            except Exception:
                if attempt == max_retries - 1:
                    self.db.rollback()
                    raise
                self.db.rollback()
                time.sleep(0.1 * 2**attempt)
                logger.info(f"Retrying on integrity error (attempt {attempt + 1}/{max_retries})")
        return fn(self, *args, **kwargs)

    return wrapper


class ContextMessageStore:
    def __init__(self, read_store: ContextMessageReadStore):
        self.read_store = read_store
        self.db = read_store.db
        self.user_id = read_store.user_id

    def persist_messages(self, messages: Iterable[ContextMessage]) -> Iterator[int]:
        for msg in messages:
            if not msg.content and not msg.tool_calls:
                logger.info(f"Skipping message with no content or tool calls: {msg}\n{traceback.format_exc()}")
            elif msg.id:
                yield msg.id
            else:
                db_message = self.db.persist(context_message_to_db_message(self.user_id, msg))
                assert db_message.id
                yield db_message.id

    def replace_context_messages(self, messages: Iterable[ContextMessage]) -> None:
        msg_ids = list(self.persist_messages(messages))

        existing_context = self.db.exec(
            select(ContextMessageSet).where(
                ContextMessageSet.user_id == self.user_id,
                cast(Any, ContextMessageSet.is_active),
            )
        ).first()

        if existing_context:
            existing_context.is_active = None
            self.db.add(existing_context)
            self.db.session.flush()

        new_context = ContextMessageSet(
            user_id=self.user_id,
            message_ids=json.dumps(msg_ids),
            is_active=True,
        )
        self.db.add(new_context)
        self.db.commit()

    @retry_on_integrity_error
    def remove_context_messages(self, messages: list[ContextMessage]) -> None:
        if not messages:
            return

        logger.info(f"Removing {len(messages)} messages")
        assert all(m.id is not None for m in messages), "All messages must have an id to be removed"

        msg_ids = [m.id for m in messages]
        self.replace_context_messages([m for m in self.read_store.get_context_messages() if m.id not in msg_ids])
