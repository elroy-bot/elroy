import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, cast

from sqlmodel import select
from toolz import first

from ...core.constants import USER
from ...db.db_models import ContextMessageSet
from ...db.db_session import DbSession
from ...repository.context_messages.data_models import ContextMessage
from ...repository.context_messages.transforms import ContextMessageSetWithMessages, context_message_to_db_message


@dataclass
class ContextMessageWriteHooks:
    get_or_create_memory_tracker: Callable[[], Any] | None = None
    persist_memory_tracker: Callable[[Any], Any] | None = None
    schedule_memory_creation: Callable[[], None] | None = None


class ContextMessageQueryService:
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
        """
        Gets context messages from db, in order of their position in ContextMessageSet
        """

        yield from self.get_or_create_context_message_set().messages

    def get_current_system_instruct(self) -> ContextMessage | None:
        try:
            return first(self.get_context_messages())
        except StopIteration:
            return None


class ContextMessageOperationService:
    def __init__(
        self,
        db: DbSession,
        user_id: int,
        *,
        query_service: ContextMessageQueryService | None = None,
        messages_between_memory: int | None = None,
        hooks: ContextMessageWriteHooks | None = None,
    ):
        self.db = db
        self.user_id = user_id
        self.query_service = query_service or ContextMessageQueryService(db, user_id)
        self.messages_between_memory = messages_between_memory
        self.hooks = hooks or ContextMessageWriteHooks()

    def persist_messages(self, messages: Iterable[ContextMessage]) -> Iterable[int]:
        for msg in messages:
            if not msg.content and not msg.tool_calls:
                continue
            if msg.id:
                yield msg.id
                continue

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

    def remove_context_messages(self, messages: list[ContextMessage]) -> None:
        if not messages:
            return

        assert all(m.id is not None for m in messages), "All messages must have an id to be removed"
        msg_ids = {m.id for m in messages}
        self.replace_context_messages(m for m in self.query_service.get_context_messages() if m.id not in msg_ids)

    def add_context_messages(self, messages: Iterable[ContextMessage]) -> None:
        msgs_list = list(messages)
        user_and_asst_msgs_ct = len([msg for msg in msgs_list if msg.role == USER and msg.content])

        self.replace_context_messages([*self.query_service.get_context_messages(), *msgs_list])

        if (
            user_and_asst_msgs_ct > 0
            and self.messages_between_memory is not None
            and self.hooks.get_or_create_memory_tracker
            and self.hooks.persist_memory_tracker
        ):
            tracker = self.hooks.get_or_create_memory_tracker()
            tracker.messages_since_memory += user_and_asst_msgs_ct
            tracker = self.hooks.persist_memory_tracker(tracker)

            if tracker.messages_since_memory >= self.messages_between_memory and self.hooks.schedule_memory_creation:
                self.hooks.schedule_memory_creation()


def context_message_operation_service_for_context(ctx: Any) -> ContextMessageOperationService:
    from ...core.async_tasks import schedule_task
    from ...repository.memories.operations import create_mem_from_current_context, get_or_create_memory_op_tracker

    return ContextMessageOperationService(
        ctx.db,
        ctx.user_id,
        query_service=ContextMessageQueryService(ctx.db, ctx.user_id),
        messages_between_memory=ctx.messages_between_memory,
        hooks=ContextMessageWriteHooks(
            get_or_create_memory_tracker=lambda: get_or_create_memory_op_tracker(ctx),
            persist_memory_tracker=lambda tracker: ctx.db.persist(tracker),
            schedule_memory_creation=lambda: schedule_task(create_mem_from_current_context, ctx),
        ),
    )
