from typing import Optional
from unittest.mock import AsyncMock

import pytest
from sqlmodel import select

from elroy.config.ctx import ElroyContext
from elroy.db.db_models import Memory
from elroy.repository.memory import consolidate_memories, create_memory


@pytest.mark.asyncio
async def test_identical_memories(ctx):
    """Test consolidation of identical memories marks one inactive"""
    memory1_id = create_memory(
        ctx, "User's Hiking Habits", "User mentioned they enjoy hiking in the mountains and try to go every weekend."
    )
    memory2_id = create_memory(
        ctx, "User's Mountain Activities", "User mentioned they enjoy hiking in the mountains and try to go every weekend."
    )

    memory1 = get_memory_by_id(ctx, memory1_id)
    memory2 = get_memory_by_id(ctx, memory2_id)
    assert memory1 and memory2

    await consolidate_memories(ctx, memory1, memory2)

    memory2_after = get_memory_by_id(ctx, memory2_id)
    assert memory2_after and not memory2_after.is_active


@pytest.mark.asyncio
async def test_well_formatted_consolidation(ctx):
    """Test consolidation with well-formatted LLM response combining related hiking memories"""
    ctx.query_llm = AsyncMock(
        return_value="""# Memory Consolidation Reasoning
These memories both discuss the user's hiking activities and should be combined into a more comprehensive memory about their hiking preferences and experiences.

## User's Hiking Preferences and Experience
The user is an avid hiker who enjoys both day hikes and overnight camping. They prefer mountain trails and typically hike every weekend when weather permits. They have experience with both summer and winter hiking conditions and own proper gear for both seasons."""
    )

    memory1_id = create_memory(
        ctx, "User's Hiking Schedule", "User goes hiking every weekend and owns proper hiking gear for different seasons."
    )
    memory2_id = create_memory(
        ctx, "User's Trail Preferences", "User enjoys mountain trails and sometimes does overnight camping during their hikes."
    )

    memory1 = get_memory_by_id(ctx, memory1_id)
    memory2 = get_memory_by_id(ctx, memory2_id)
    assert memory1 and memory2

    await consolidate_memories(ctx, memory1, memory2)

    memory1_after = get_memory_by_id(ctx, memory1_id)
    memory2_after = get_memory_by_id(ctx, memory2_id)
    assert memory1_after and not memory1_after.is_active
    assert memory2_after and not memory2_after.is_active


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

    memory1_id = create_memory(ctx, "User's Morning Coffee", "User drinks black dark roast coffee every morning.")
    memory2_id = create_memory(ctx, "User's Afternoon Coffee", "User enjoys lighter roasts in the afternoon with oat milk.")

    memory1 = get_memory_by_id(ctx, memory1_id)
    memory2 = get_memory_by_id(ctx, memory2_id)
    assert memory1 and memory2

    await consolidate_memories(ctx, memory1, memory2)

    memory1_after = get_memory_by_id(ctx, memory1_id)
    memory2_after = get_memory_by_id(ctx, memory2_id)
    assert memory1_after and not memory1_after.is_active
    assert memory2_after and not memory2_after.is_active


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

    memory1_id = create_memory(
        ctx, "User's Python Experience", "User has been coding in Python for 5+ years and uses it for data analysis."
    )
    memory2_id = create_memory(ctx, "User's Musical Background", "User played piano as a child and recently started taking lessons again.")

    memory1 = get_memory_by_id(ctx, memory1_id)
    memory2 = get_memory_by_id(ctx, memory2_id)
    assert memory1 and memory2

    await consolidate_memories(ctx, memory1, memory2)

    memory1_after = get_memory_by_id(ctx, memory1_id)
    memory2_after = get_memory_by_id(ctx, memory2_id)
    assert memory1_after and not memory1_after.is_active
    assert memory2_after and not memory2_after.is_active


@pytest.mark.asyncio
async def test_missing_reasoning_section(ctx):
    """Test consolidation without reasoning section but with clear memory structure"""
    ctx.query_llm = AsyncMock(
        return_value="""## User's Tea Preferences
The user enjoys both green and black teas, preferring green tea in the morning for its lighter caffeine content and black tea in the afternoon for a stronger boost. They always brew loose leaf tea rather than using tea bags.

## User's Tea Preparation Method
They have a precise brewing routine, using water at exactly 175°F for green tea and 205°F for black tea, and timing each steep carefully with a timer."""
    )

    memory1_id = create_memory(
        ctx, "User's Tea Preferences", "User drinks green tea in morning and black tea in afternoon, always loose leaf."
    )
    memory2_id = create_memory(
        ctx, "User's Tea Preparation", "User is precise about tea temperatures: 175°F for green and 205°F for black."
    )

    memory1 = get_memory_by_id(ctx, memory1_id)
    memory2 = get_memory_by_id(ctx, memory2_id)
    assert memory1 and memory2

    await consolidate_memories(ctx, memory1, memory2)

    memory1_after = get_memory_by_id(ctx, memory1_id)
    memory2_after = get_memory_by_id(ctx, memory2_id)
    assert memory1_after and not memory1_after.is_active
    assert memory2_after and not memory2_after.is_active


def get_memory_by_id(ctx: ElroyContext, memory_id: int) -> Optional[Memory]:
    """Fetch a specific memory by ID"""
    return ctx.db.exec(select(Memory).where(Memory.id == memory_id, Memory.user_id == ctx.user_id)).first()
