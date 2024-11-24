import asyncio

from elroy.cli.context import get_user_logged_in_message
from elroy.messaging.context import context_refresh
from elroy.repository.memory import get_active_memories


def test_context_refresh(george_context):
    before_memory_count = len(get_active_memories(george_context))

    asyncio.run(context_refresh(george_context))

    assert len(get_active_memories(george_context)) == before_memory_count + 1


def test_user_login_msg(onboarded_context):
    get_user_logged_in_message(onboarded_context)
    # TODO: more specific test that takes context into account (with test clock)
