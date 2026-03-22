import logging
import time
from typing import Any, cast

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import delete, select

from elroy.core.constants import USER
from elroy.core.ctx import ElroyContext
from elroy.db.db_models import ContextMessageSet
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.operations import (
    add_context_messages,
    pop,
    remove_context_messages,
)
from elroy.repository.context_messages.queries import (
    get_context_messages,
    get_or_create_context_message_set,
)
from elroy.utils.utils import run_in_background


@pytest.mark.filterwarnings("error")
def test_rm_context_messages(george_ctx: ElroyContext):
    msgs = list(get_context_messages(george_ctx))

    to_rm = msgs[-3:]
    for msg in to_rm:
        # Concurrent removals
        run_in_background(remove_context_messages, george_ctx, [msg])

    attempts = 0
    max_attempts = 5
    while attempts < max_attempts:
        try:
            new_msgs = list(get_context_messages(george_ctx))
            assert not any(msg in new_msgs for msg in to_rm)
            assert len(new_msgs) == len(msgs) - len(to_rm)
            break
        except Exception:
            logging.info("Msgs not yet removed, retrying...")
            attempts += 1
            time.sleep(1)


@pytest.mark.filterwarnings("error")
def test_add_context_messages(george_ctx: ElroyContext):
    msgs = list(get_context_messages(george_ctx))

    to_add = [
        ContextMessage(
            role=USER,
            content=f"test message {_}",
            chat_model=george_ctx.chat_model.name,
        )
        for _ in range(4)
    ]
    for msg in to_add:
        # Concurrent removals
        run_in_background(add_context_messages, george_ctx, [msg])

    attempts = 0
    max_attempts = 5
    while attempts < max_attempts:
        try:
            new_msgs = [msg.content for msg in get_context_messages(george_ctx)]
            assert all(msg.content in new_msgs for msg in to_add)
            assert len(new_msgs) == len(msgs) + len(to_add)
            break
        except Exception:
            logging.info("Msgs not yet removed, retrying...")
            attempts += 1
            time.sleep(1)


def test_pop(george_ctx: ElroyContext):
    original_len = len(list(get_context_messages(george_ctx)))

    pop(george_ctx, 2)

    assert len(list(get_context_messages(george_ctx))) == original_len - 2


def test_get_or_create_context_message_set_recovers_after_failed_create(ctx: ElroyContext, monkeypatch: pytest.MonkeyPatch):
    ctx.db.exec(delete(ContextMessageSet).where(cast(Any, ContextMessageSet.user_id) == ctx.user_id))
    ctx.db.commit()

    real_commit = ctx.db.session.commit
    attempts = 0

    def flaky_commit():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise IntegrityError("insert into contextmessageset", {}, Exception("simulated create failure"))
        return real_commit()

    monkeypatch.setattr(ctx.db.session, "commit", flaky_commit)

    context_message_set = get_or_create_context_message_set(ctx)
    assert context_message_set.id is not None
    assert list(get_context_messages(ctx)) == []

    active_contexts = list(
        ctx.db.exec(
            select(ContextMessageSet).where(
                ContextMessageSet.user_id == ctx.user_id,
                cast(Any, ContextMessageSet.is_active).is_(True),
            )
        ).all()
    )
    assert len(active_contexts) == 1
    assert get_or_create_context_message_set(ctx).id == context_message_set.id
