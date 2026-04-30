from functools import partial

from sqlmodel import select
from toolz import pipe
from toolz.curried import filter, map

from elroy.core.session import open_turn_context
from elroy.db.db_models import Memory, MemoryOperationTracker
from elroy.repository.memories.consolidation import (
    MemoryCluster,
    consolidate_memory_cluster,
)
from elroy.repository.memories.factory import build_memory_lifecycle_orchestrator
from elroy.repository.memories.queries import get_active_memories, get_memory_by_name
from elroy.repository.user.session import build_user_session


def test_identical_memories(ctx):
    """Test consolidation of identical memories marks one inactive"""
    with open_turn_context(ctx) as turn:
        memory_lifecycle_orchestrator = build_memory_lifecycle_orchestrator(turn)
        memory1 = memory_lifecycle_orchestrator.do_create_memory_from_ctx_msgs(
            "User's Hiking Habits", "User mentioned they enjoy hiking in the mountains and try to go every weekend."
        )
        memory2 = memory_lifecycle_orchestrator.do_create_memory_from_ctx_msgs(
            "User's Mountain Activities", "User mentioned they enjoy hiking in the mountains and try to go every weekend."
        )

    assert memory1 and memory2

    consolidate_memory_cluster(ctx, get_cluster(ctx, [memory1, memory2]))

    memory2 = get_memory_by_name(ctx, memory2.name)

    assert memory2 is None  # doesn't get returned, since it is now inactive


def test_trigger(ctx):
    ctx.use_background_threads = False
    assert ctx.memories_between_consolidation == 4

    with open_turn_context(ctx) as turn:
        memory_lifecycle_orchestrator = build_memory_lifecycle_orchestrator(turn)
        pipe(
            [
                "I went to the store today, January 1",
                "I went shopping at the store on New Year' Day",
                "Today, New Year's Day, I went to the store",
                "I bought some items on New Year's Day",
            ],
            map(partial(memory_lifecycle_orchestrator.do_create_memory_from_ctx_msgs, "Shopping Trip")),
            filter(lambda x: x is not None),
            list,
        )

    assert len(get_active_memories(ctx)) == 1
    with open_turn_context(ctx) as turn:
        user_session = build_user_session(turn)
        assert (
            user_session.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == user_session.user_id))
            .first()
            .memories_since_consolidation
            == 0
        )


def get_cluster(ctx, memories: list[Memory]) -> MemoryCluster:
    with open_turn_context(ctx) as turn:
        user_session = build_user_session(turn)
        return MemoryCluster(
            memories=memories,
            embeddings=[user_session.db.get_embedding(memory) for memory in memories],  # type: ignore
        )
