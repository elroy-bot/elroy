import logging
import time
from functools import partial
from typing import List

from sqlmodel import select
from toolz import pipe
from toolz.curried import filter, map

from elroy.db.db_models import Memory, MemoryOperationTracker
from elroy.repository.memories.consolidation import (
    MemoryCluster,
    consolidate_memory_cluster,
)
from elroy.repository.memories.operations import do_create_memory_from_ctx_msgs
from elroy.repository.memories.queries import get_active_memories


def test_identical_memories(ctx):
    """Test consolidation of identical memories marks one inactive"""
    memory1 = do_create_memory_from_ctx_msgs(
        ctx, "User's Hiking Habits", "User mentioned they enjoy hiking in the mountains and try to go every weekend."
    )[0]
    memory2 = do_create_memory_from_ctx_msgs(
        ctx, "User's Mountain Activities", "User mentioned they enjoy hiking in the mountains and try to go every weekend."
    )[0]

    assert memory1 and memory2

    consolidate_memory_cluster(ctx, get_cluster(ctx, [memory1, memory2]))

    ctx.db.refresh(memory1)
    ctx.db.refresh(memory2)

    assert not memory2.is_active


def test_trigger(ctx):
    assert ctx.memories_between_consolidation == 4

    threads = pipe(
        [
            "I went to the store today, January 1",
            "I went shopping at the store on New Year' Day",
            "Today, New Year's Day, I went to the store",
            "I bought some items on New Year's Day",
        ],
        map(partial(do_create_memory_from_ctx_msgs, ctx, "Shopping Trip")),
        map(lambda x: x[1]),
        filter(lambda x: x is not None),
        list,
    )

    assert len(threads) > 0, "No threads created for consolidation test"

    max_retries = 10
    retry_count = 0
    live_thread_count = len(threads)
    while retry_count < max_retries:
        live_thread_count = len([thread for thread in threads if thread.is_alive()])  # type: ignore
        if live_thread_count == 0:
            break
        else:
            logging.info(f"Waiting for {live_thread_count} consolidation threads to complete...")
            time.sleep(0.5)

    assert live_thread_count == 0, "Consolidation threads did not complete in time"

    assert len(get_active_memories(ctx)) == 1
    assert (
        ctx.db.exec(select(MemoryOperationTracker).where(MemoryOperationTracker.user_id == ctx.user_id))
        .first()
        .memories_since_consolidation
        == 0
    )


def get_cluster(ctx, memories: List[Memory]) -> MemoryCluster:
    return MemoryCluster(
        memories=memories,
        embeddings=[ctx.db.get_embedding(memory) for memory in memories],  # type: ignore
    )
