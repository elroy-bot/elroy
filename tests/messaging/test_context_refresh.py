import asyncio

from elroy.cli.context import get_user_logged_in_message
from elroy.messaging.context import context_refresh
from elroy.repository.memories.operations import get_active_memories


def test_context_refresh(george_ctx):
    before_memory_count = len(get_active_memories(george_ctx))

    asyncio.run(context_refresh(george_ctx))

    assert len(get_active_memories(george_ctx)) == before_memory_count + 1


def test_user_login_msg(ctx):
    get_user_logged_in_message(ctx)
    # TODO: more specific test that takes context into account (with test clock)
