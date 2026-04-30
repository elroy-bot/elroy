from sqlmodel import select

from elroy.core.ctx import ElroyConfig
from elroy.core.session import invoke_with_config, open_turn_context
from elroy.db.db_models import Memory
from elroy.repository.memories.factory import build_memory_lifecycle_orchestrator
from elroy.repository.memories.queries import get_memory_by_name
from elroy.repository.memories.tools import update_outdated_or_incorrect_memory
from elroy.repository.user.session import build_user_session


def test_update_memory_creates_new_active_version(george_ctx: ElroyConfig):
    with open_turn_context(george_ctx) as turn:
        original_mem = build_memory_lifecycle_orchestrator(turn).do_create_memory_from_ctx_msgs(
            "George's relationship status", "George got engaged to Sarah on 2025-01-01"
        )

    result = invoke_with_config(
        update_outdated_or_incorrect_memory,
        george_ctx,
        memory_name="George's relationship status",
        update_text="George got married to Sarah on 2025-02-01",
    )

    assert result == "Memory 'George's relationship status' has been updated"

    updated_memory = get_memory_by_name(george_ctx, "George's relationship status")
    assert updated_memory is not None
    assert updated_memory.id != original_mem.id

    with open_turn_context(george_ctx) as turn:
        user_session = build_user_session(turn)
        memories = list(
            user_session.db.exec(
                select(Memory).where(
                    Memory.user_id == user_session.user_id,
                    Memory.name == "George's relationship status",
                )
            ).all()
        )

    assert len(memories) == 2

    old_memory = next(memory for memory in memories if memory.id == original_mem.id)
    new_memory = next(memory for memory in memories if memory.id == updated_memory.id)

    assert old_memory.is_active is False
    assert new_memory.is_active is True
    assert "George got engaged to Sarah on 2025-01-01" in new_memory.to_fact()
    assert "George got married to Sarah on 2025-02-01" in new_memory.to_fact()
