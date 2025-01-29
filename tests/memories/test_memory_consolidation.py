import asyncio
import logging
from typing import List
from unittest.mock import AsyncMock

import pytest
from sqlmodel import select

from elroy.db.db_models import Memory, MemoryOperationTracker
from elroy.repository.memories.consolidation import (
    MemoryCluster,
    consolidate_memory_cluster,
)
from elroy.repository.memories.operations import create_memory, do_create_memory
from elroy.repository.memories.queries import get_active_memories


@pytest.mark.asyncio
async def test_identical_memories(ctx):
    """Test consolidation of identical memories marks one inactive"""
    memory1 = do_create_memory(
        ctx, "User's Hiking Habits", "User mentioned they enjoy hiking in the mountains and try to go every weekend."
    )
    memory2 = do_create_memory(
        ctx, "User's Mountain Activities", "User mentioned they enjoy hiking in the mountains and try to go every weekend."
    )

    assert memory1 and memory2

    await consolidate_memory_cluster(ctx, get_cluster(ctx, [memory1, memory2]))

    ctx.db.refresh(memory1)
    ctx.db.refresh(memory2)

    assert not memory2.is_active


@pytest.mark.asyncio
async def test_well_formatted_consolidation(ctx):
    """Test consolidation with well-formatted LLM response combining related hiking memories"""
    ctx.query_llm = AsyncMock(
        return_value="""# Memory Consolidation Reasoning
These memories both discuss the user's hiking activities and should be combined into a more comprehensive memory about their hiking preferences and experiences.

## User's Hiking Preferences and Experience
The user is an avid hiker who enjoys both day hikes and overnight camping. They prefer mountain trails and typically hike every weekend when weather permits. They have experience with both summer and winter hiking conditions and own proper gear for both seasons."""
    )

    memory1 = do_create_memory(
        ctx, "User's Hiking Schedule", "User goes hiking every weekend and owns proper hiking gear for different seasons."
    )
    memory2 = do_create_memory(
        ctx, "User's Trail Preferences", "User enjoys mountain trails and sometimes does overnight camping during their hikes."
    )

    assert memory1 and memory2

    await consolidate_memory_cluster(ctx, get_cluster(ctx, [memory1, memory2]))

    assert not memory1.is_active
    assert not memory2.is_active


@pytest.mark.asyncio
async def test_malformed_response_still_creates_memory(ctx):
    """Test consolidation still works with malformed response that has minimal structure"""
    ctx.query_llm = AsyncMock(
        return_value="""Here's my thoughts on combining these memories:
The user clearly has two distinct preferences for coffee.

# Their Morning Coffee Routine
They prefer dark roast coffee first thing in the morning, always black.

# Their Afternoon Coffee
They enjoy lighter roasts in the afternoon, sometimes with a splash of oat milk."""
    )

    memory1 = do_create_memory(ctx, "User's Morning Coffee", "User drinks black dark roast coffee every morning.")
    memory2 = do_create_memory(ctx, "User's Afternoon Coffee", "User enjoys lighter roasts in the afternoon with oat milk.")

    assert memory1 and memory2

    await consolidate_memory_cluster(ctx, get_cluster(ctx, [memory1, memory2]))

    assert not memory1.is_active
    assert not memory2.is_active


@pytest.mark.asyncio
async def test_split_unrelated_memories(ctx):
    """Test consolidation that correctly splits unrelated topics"""
    ctx.query_llm = AsyncMock(
        return_value="""# Consolidation Reasoning
These memories cover two distinct topics and should be kept separate for clarity.

## User's Programming Language Preference
The user primarily codes in Python and has been using it professionally for over 5 years. They particularly enjoy using it for data analysis and automation tasks.

## User's Musical Background
The user played piano for 10 years during their childhood and recently started taking lessons again to refresh their skills."""
    )

    memory1 = do_create_memory(
        ctx, "User's Python Experience", "User has been coding in Python for 5+ years and uses it for data analysis."
    )
    memory2 = do_create_memory(ctx, "User's Musical Background", "User played piano as a child and recently started taking lessons again.")

    assert memory1 and memory2

    await consolidate_memory_cluster(ctx, get_cluster(ctx, [memory1, memory2]))

    assert not memory1.is_active
    assert not memory2.is_active


@pytest.mark.asyncio
async def test_missing_reasoning_section(ctx):
    """Test consolidation without reasoning section but with clear memory structure"""
    ctx.query_llm = AsyncMock(
        return_value="""## User's Tea Preferences
The user enjoys both green and black teas, preferring green tea in the morning for its lighter caffeine content and black tea in the afternoon for a stronger boost. They always brew loose leaf tea rather than using tea bags.

## User's Tea Preparation Method
They have a precise brewing routine, using water at exactly 175°F for green tea and 205°F for black tea, and timing each steep carefully with a timer."""
    )

    memory1 = do_create_memory(
        ctx, "User's Tea Preferences", "User drinks green tea in morning and black tea in afternoon, always loose leaf."
    )
    memory2 = do_create_memory(
        ctx, "User's Tea Preparation", "User is precise about tea temperatures: 175°F for green and 205°F for black."
    )

    assert memory1 and memory2

    await consolidate_memory_cluster(ctx, get_cluster(ctx, [memory1, memory2]))

    assert not memory1.is_active
    assert not memory2.is_active


@pytest.mark.asyncio
async def test_trigger(ctx):
    assert ctx.memories_between_consolidation == 4

    for text in [
        "I went to the store today, January 1",
        "I went shopping at the store on New Year' Day",
        "Today, New Year's Day, I went to the store",
        "I bought some items on New Year's Day",
    ]:
        create_memory(ctx, "Shopping Trip", text)

    # Polling mechanism to wait for consolidation to complete
    max_retries = 10
    retry_count = 0
    while retry_count < max_retries:
        await asyncio.sleep(0.5)  # Wait for a short period before checking again
        if len(get_active_memories(ctx)) == 1:
            break
        retry_count += 1
        logging.info("Waiting for consolidation to complete...")

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
