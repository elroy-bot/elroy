"""
Unit tests for the embeddings cache implementation using JSON format.
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from elroy.llm.embedding_cache import EmbeddingCache


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir) / "test_cache" / "embeddings"
        cache_dir.mkdir(parents=True)
        yield cache_dir


@pytest.fixture
def cache(temp_cache_dir):
    """Create a cache instance for testing."""
    with patch('elroy.llm.embedding_cache.get_cache_dir') as mock_get_cache_dir:
        mock_get_cache_dir.return_value = temp_cache_dir.parent
        cache = EmbeddingCache(max_size_mb=1)  # Small size for testing
        yield cache


def test_cache_miss(cache):
    """Test cache miss returns None."""
    result = cache.get("test-model", "test text")
    assert result is None


def test_cache_hit(cache):
    """Test cache hit returns stored embedding."""
    embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    
    # Store embedding
    cache.put("test-model", "test text", embedding)
    
    # Retrieve embedding
    result = cache.get("test-model", "test text")
    assert result == embedding


def test_cache_different_models(cache):
    """Test that different models have separate cache entries."""
    embedding1 = [0.1, 0.2, 0.3]
    embedding2 = [0.4, 0.5, 0.6]
    
    cache.put("model1", "same text", embedding1)
    cache.put("model2", "same text", embedding2)
    
    assert cache.get("model1", "same text") == embedding1
    assert cache.get("model2", "same text") == embedding2


def test_cache_different_texts(cache):
    """Test that different texts have separate cache entries."""
    embedding1 = [0.1, 0.2, 0.3]
    embedding2 = [0.4, 0.5, 0.6]
    
    cache.put("same-model", "text1", embedding1)
    cache.put("same-model", "text2", embedding2)
    
    assert cache.get("same-model", "text1") == embedding1
    assert cache.get("same-model", "text2") == embedding2


def test_cache_persistence(temp_cache_dir):
    """Test that cache persists across instances."""
    embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    
    with patch('elroy.llm.embedding_cache.get_cache_dir') as mock_get_cache_dir:
        mock_get_cache_dir.return_value = temp_cache_dir.parent
        
        # First cache instance
        cache1 = EmbeddingCache(max_size_mb=1)
        cache1.put("test-model", "test text", embedding)
        
        # Second cache instance (simulates app restart)
        cache2 = EmbeddingCache(max_size_mb=1)
        result = cache2.get("test-model", "test text")
        assert result == embedding


def test_fifo_eviction(cache):
    """Test FIFO eviction when size limit is reached."""
    # Create embeddings that will exceed the 1MB limit
    large_embedding = [0.1] * 50000  # ~50k floats = ~400KB in JSON
    
    # Add multiple entries to exceed size limit
    cache.put("model", "text1", large_embedding)
    cache.put("model", "text2", large_embedding)
    cache.put("model", "text3", large_embedding)  # This should trigger eviction
    
    # First entry should be evicted (FIFO)
    assert cache.get("model", "text1") is None
    assert cache.get("model", "text2") == large_embedding
    assert cache.get("model", "text3") == large_embedding


def test_access_order_updates(cache):
    """Test that access order is updated on cache hits."""
    embedding1 = [0.1, 0.2, 0.3]
    embedding2 = [0.4, 0.5, 0.6]
    
    # Add two entries
    cache.put("model", "text1", embedding1)
    time.sleep(0.01)  # Ensure different timestamps
    cache.put("model", "text2", embedding2)
    
    # Access first entry (should move it to end of access order)
    cache.get("model", "text1")
    
    # Verify access order was updated in index
    assert cache.access_order[-1] == cache._get_cache_key("model", "text1")


def test_clear_cache(cache):
    """Test clearing all cache entries."""
    cache.put("model1", "text1", [0.1, 0.2])
    cache.put("model2", "text2", [0.3, 0.4])
    
    # Verify entries exist
    assert cache.get("model1", "text1") == [0.1, 0.2]
    assert cache.get("model2", "text2") == [0.3, 0.4]
    
    # Clear cache
    cache.clear()
    
    # Verify entries are gone
    assert cache.get("model1", "text1") is None
    assert cache.get("model2", "text2") is None
    assert len(cache.index) == 0
    assert len(cache.access_order) == 0


def test_cache_stats(cache):
    """Test cache statistics reporting."""
    initial_stats = cache.get_stats()
    assert initial_stats['entries'] == 0
    assert initial_stats['size_bytes'] >= 0  # Index file might exist
    
    # Add an entry
    embedding = [0.1, 0.2, 0.3]
    cache.put("test-model", "test text", embedding)
    
    stats = cache.get_stats()
    assert stats['entries'] == 1
    assert stats['size_bytes'] > initial_stats['size_bytes']
    assert stats['size_mb'] > 0
    assert 0 <= stats['utilization_percent'] <= 100


def test_json_format_compatibility(cache, temp_cache_dir):
    """Test that cache files are in valid JSON format."""
    embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    cache.put("test-model", "test text", embedding)
    
    # Find the cache file
    cache_files = list((temp_cache_dir / "embeddings").glob("*.json"))
    assert len(cache_files) == 1
    
    # Verify it's valid JSON
    with open(cache_files[0]) as f:
        data = json.load(f)
    
    assert data['model'] == "test-model"
    assert data['text'] == "test text"
    assert data['embedding'] == embedding
    assert 'created_at' in data


def test_corrupted_cache_file_handling(cache, temp_cache_dir):
    """Test handling of corrupted cache files."""
    # Create a corrupted cache file
    cache_key = cache._get_cache_key("test-model", "test text")
    cache_file = cache._get_cache_file_path(cache_key)
    
    # Write invalid JSON
    with open(cache_file, 'w') as f:
        f.write("invalid json content")
    
    # Add entry to index (simulating a corrupted state)
    cache.index[cache_key] = {
        'created_at': time.time(),
        'last_accessed': time.time(),
        'model': 'test-model'
    }
    
    # Should handle corruption gracefully
    result = cache.get("test-model", "test text")
    assert result is None


def test_missing_cache_file_handling(cache):
    """Test handling when cache file is missing but index entry exists."""
    cache_key = cache._get_cache_key("test-model", "test text")
    
    # Add index entry without creating file
    cache.index[cache_key] = {
        'created_at': time.time(),
        'last_accessed': time.time(),
        'model': 'test-model'
    }
    cache.access_order.append(cache_key)
    
    # Should clean up stale index entry
    result = cache.get("test-model", "test text")
    assert result is None
    assert cache_key not in cache.index
    assert cache_key not in cache.access_order


def test_cache_key_generation(cache):
    """Test cache key generation is consistent."""
    key1 = cache._get_cache_key("model1", "text1")
    key2 = cache._get_cache_key("model1", "text1")
    key3 = cache._get_cache_key("model2", "text1")
    key4 = cache._get_cache_key("model1", "text2")
    
    assert key1 == key2  # Same model and text
    assert key1 != key3  # Different model
    assert key1 != key4  # Different text


def test_empty_text_handling(cache):
    """Test that empty text is handled correctly."""
    embedding = [0.1, 0.2, 0.3]
    
    # Should be able to cache empty text
    cache.put("test-model", "", embedding)
    result = cache.get("test-model", "")
    assert result == embedding


def test_large_embedding_handling(cache):
    """Test handling of large embeddings (like those from large models)."""
    # Test with a large embedding (simulating models with 1536+ dimensions)
    large_embedding = [float(i) * 0.001 for i in range(1536)]
    
    cache.put("large-model", "test text", large_embedding)
    result = cache.get("large-model", "test text")
    assert result == large_embedding


def test_thread_safety_simulation(cache):
    """Basic test for thread safety (single-threaded simulation)."""
    import threading
    
    embeddings = []
    
    def cache_operation(i):
        embedding = [float(i)] * 10
        cache.put(f"model-{i}", f"text-{i}", embedding)
        result = cache.get(f"model-{i}", f"text-{i}")
        embeddings.append(result)
    
    # Simulate concurrent operations
    threads = []
    for i in range(5):
        thread = threading.Thread(target=cache_operation, args=(i,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    # Verify all operations completed successfully
    assert len(embeddings) == 5
    for i, embedding in enumerate(embeddings):
        assert embedding == [float(i)] * 10