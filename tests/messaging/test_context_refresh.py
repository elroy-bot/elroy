from elroy.cli.chat import get_session_context
from elroy.core.session import open_turn_context
from elroy.repository.context_messages.factory import build_context_refresh_orchestrator
from elroy.repository.context_messages.queries import get_context_messages
from elroy.repository.context_messages.session import build_context_message_session
from elroy.repository.memories.queries import get_active_memories


def test_context_refresh(george_ctx):
    before_memory_count = len(get_active_memories(george_ctx))

    context_messages = get_context_messages(george_ctx)
    with open_turn_context(george_ctx) as turn:
        build_context_refresh_orchestrator(build_context_message_session(turn)).context_refresh(context_messages)

    assert len(get_active_memories(george_ctx)) == before_memory_count + 1


def test_session_context(ctx):
    with open_turn_context(ctx) as turn:
        get_session_context(turn)
    # Future improvement: more specific test that takes context into account (with test clock)
