from datetime import datetime, timezone

import pytest
from sqlmodel import select

from elroy.db.db_models import Memory
from elroy.utils.clock import db_time_to_local


def test_update_memory_relationship_status(test_ctx):
    # Create initial memory about engagement
    memory_name = "Tom's relationship status"
    initial_text = "Tom is engaged to be married to Sarah"
    test_ctx.tools.create_memory(memory_name, initial_text)

    # Verify initial memory was created
    memory = test_ctx.db.exec(
        select(Memory)
        .where(Memory.user_id == test_ctx.user_id, Memory.name == memory_name)
    ).first()
    assert memory is not None
    assert memory.text == initial_text
    assert memory.is_active

    # Update the memory to reflect marriage
    update_text = "Tom and Sarah got married"
    test_ctx.tools.update_memory(memory_name, update_text)

    # Get all memories with this name
    memories = test_ctx.db.exec(
        select(Memory)
        .where(Memory.user_id == test_ctx.user_id, Memory.name == memory_name)
        .order_by(Memory.created_at)
    ).all()

    # Should be 2 memories - original (inactive) and updated (active)
    assert len(memories) == 2
    
    # Original memory should be inactive
    assert not memories[0].is_active
    assert memories[0].text == initial_text

    # Updated memory should be active and contain both pieces of info
    assert memories[1].is_active
    update_time = db_time_to_local(memories[0].created_at).strftime("%Y-%m-%d %H:%M:%S")
    expected_text = f"{initial_text}\n\nUpdate ({update_time}):\n{update_text}"
    assert memories[1].text == expected_text
