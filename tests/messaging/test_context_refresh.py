from elroy.cli.chat import get_session_context
from elroy.repository.context_messages.factory import build_context_refresh_orchestrator
from elroy.repository.context_messages.queries import get_context_messages
from elroy.repository.memories.queries import get_active_memories


def test_context_refresh(george_ctx):
    before_memory_count = len(get_active_memories(george_ctx))

    context_messages = get_context_messages(george_ctx)
    build_context_refresh_orchestrator(george_ctx).context_refresh(context_messages)

    assert len(get_active_memories(george_ctx)) == before_memory_count + 1


def test_session_context(ctx):
    get_session_context(ctx)
    # Future improvement: more specific test that takes context into account (with test clock)
