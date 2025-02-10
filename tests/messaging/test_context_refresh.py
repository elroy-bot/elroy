
from elroy.cli.chat import get_user_logged_in_message
from elroy.repository.context_messages.operations import context_refresh
from elroy.repository.context_messages.queries import get_context_messages
from elroy.repository.memories.queries import get_active_memories
from elroy.utils.utils import do_asyncio_run


def test_context_refresh(george_ctx):
    before_memory_count = len(get_active_memories(george_ctx))

    context_messages = get_context_messages(george_ctx)
    do_asyncio_run(context_refresh(george_ctx, context_messages))

    assert len(get_active_memories(george_ctx)) == before_memory_count + 1


def test_user_login_msg(ctx):
    get_user_logged_in_message(ctx)
    # TODO: more specific test that takes context into account (with test clock)
