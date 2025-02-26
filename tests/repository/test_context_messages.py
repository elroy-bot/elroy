import logging
import time

from elroy.config.constants import USER
from elroy.config.ctx import ElroyContext
from elroy.repository.context_messages.data_models import ContextMessage
from elroy.repository.context_messages.operations import (
    add_context_messages,
    remove_context_messages,
)
from elroy.repository.context_messages.queries import get_context_messages
from elroy.utils.utils import run_in_background


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


def test_add_context_messages(george_ctx: ElroyContext):
    msgs = list(get_context_messages(george_ctx))

    to_add = [ContextMessage(role=USER, content=f"test message {_}", chat_model=george_ctx.chat_model.name) for _ in range(4)]
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
