from elroy.core.ctx import ElroyContext
from elroy.repository.memories.operations import do_create_memory
from elroy.repository.memories.queries import get_memories
from tests.utils import MockCliIO


def test_get_memories(io: MockCliIO, ctx: ElroyContext):
    """Test that get_memories returns the correct Memory objects for given IDs"""
    # Create some test memories
    do_create_memory(ctx, "Test Memory 1", "This is the first test memory", [], False)
    do_create_memory(ctx, "Test Memory 2", "This is the second test memory", [], False)
    do_create_memory(ctx, "Test Memory 3", "This is the third test memory", [], False)

    # Extract memory IDs from the results (assuming the function returns a string with ID info)
    # We'll need to get the actual memory objects to get their IDs
    from elroy.repository.memories.queries import get_memory_by_name

    memory1 = get_memory_by_name(ctx, "Test Memory 1")
    memory2 = get_memory_by_name(ctx, "Test Memory 2")
    memory3 = get_memory_by_name(ctx, "Test Memory 3")

    assert memory1 is not None
    assert memory2 is not None
    assert memory3 is not None

    memory_1_id = memory1.id
    memory_3_id = memory3.id

    assert memory_1_id and memory_3_id

    retrieved_memories = get_memories(ctx, [memory_1_id, memory_3_id])

    # Verify we got the correct memories
    assert len(retrieved_memories) == 2
    retrieved_names = [mem.name for mem in retrieved_memories]
    assert "Test Memory 1" in retrieved_names
    assert "Test Memory 3" in retrieved_names
    assert "Test Memory 2" not in retrieved_names

    # Test with empty list
    empty_result = get_memories(ctx, [])
    assert len(empty_result) == 0

    # Test with non-existent ID
    non_existent_result = get_memories(ctx, [99999])
    assert len(non_existent_result) == 0
