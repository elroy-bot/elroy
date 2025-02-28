import pytest
from tests.utils import process_test_message, quiz_assistant_bool

from elroy.config.ctx import ElroyContext
from elroy.repository.context_messages.operations import reset_messages
from elroy.repository.memories.operations import do_create_memory_from_ctx_msgs
from elroy.repository.memories.queries import get_memory_by_name


@pytest.mark.flaky(reruns=3)
def test_update_memory_relationship_status(george_ctx: ElroyContext):
    original_mem = do_create_memory_from_ctx_msgs(george_ctx, "George's relationship status", "George got engaged to Sarah on 2025-01-01")[
        0
    ]
    reset_messages(george_ctx)

    process_test_message(george_ctx, "I have an exciting update about my relationship status. I got married to Sarah!")

    memory = get_memory_by_name(george_ctx, "George's relationship status")
    assert memory
    assert memory.id != original_mem.id

    george_ctx.db.refresh(original_mem)

    assert not original_mem.is_active

    reset_messages(george_ctx)

    process_test_message(george_ctx, "Today I went to the store with Sarah")  # this should bring the memory back into context

    quiz_assistant_bool(True, george_ctx, "Am I married")
