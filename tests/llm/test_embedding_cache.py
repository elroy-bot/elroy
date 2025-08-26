"""Tests for the embedding cache implementation."""
import tempfile
import shutil
from pathlib import Path
import pytest

from elroy.llm.embedding_cache import EmbeddingCache


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache testing."""
    temp_dir = tempfile.mkdtemp()
    cache_dir = Path(temp_dir) / "cache" / "embeddings"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    yield cache_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def cache(temp_cache_dir):
    """Create a cache instance for testing."""
    cache = EmbeddingCache.__new__(EmbeddingCache)
    cache.max_size_bytes = 1024 * 1024  # 1MB for testing
    cache.cache_dir = temp_cache_dir
    cache.index_file = temp_cache_dir / "index.json"
    cache._load_index()
    return cache


def test_cache_miss(cache):
    """Test that cache returns None for missing entries."""
    result = cache.get("test-model", "hello world")
    assert result is None


def test_cache_put_and_get(cache):
    """Test basic cache put and get operations."""
    test_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    cache.put("test-model", "hello world", test_embedding)
    
    result = cache.get("test-model", "hello world")
    assert result == test_embedding


def test_different_keys_isolated(cache):
    """Test that different keys don't interfere with each other."""
    embedding1 = [0.1, 0.2, 0.3]
    embedding2 = [0.4, 0.5, 0.6]
    
    cache.put("test-model", "text1", embedding1)
    cache.put("test-model", "text2", embedding2)
    
    assert cache.get("test-model", "text1") == embedding1
    assert cache.get("test-model", "text2") == embedding2
    assert cache.get("test-model", "text3") is None


def test_different_models_isolated(cache):
    """Test that different models have separate cache spaces."""
    embedding = [0.1, 0.2, 0.3]
    
    cache.put("model1", "hello", embedding)
    cache.put("model2", "hello", [0.4, 0.5, 0.6])
    
    assert cache.get("model1", "hello") == embedding
    assert cache.get("model2", "hello") == [0.4, 0.5, 0.6]


def test_cache_stats(cache):
    """Test cache statistics reporting."""
    stats = cache.get_stats()
    assert stats["total_entries"] == 0
    assert stats["total_size_bytes"] == 0
    
    cache.put("test-model", "hello", [0.1, 0.2, 0.3])
    
    stats = cache.get_stats()
    assert stats["total_entries"] == 1
    assert stats["total_size_bytes"] > 0


def test_cache_clear(cache):
    """Test cache clearing functionality."""
    cache.put("test-model", "hello", [0.1, 0.2, 0.3])
    assert cache.get("test-model", "hello") is not None
    
    cache.clear()
    
    assert cache.get("test-model", "hello") is None
    stats = cache.get_stats()
    assert stats["total_entries"] == 0
    assert stats["total_size_bytes"] == 0


def test_fifo_eviction(cache):
    """Test FIFO eviction policy."""
    # Set very small cache size
    cache.max_size_bytes = 200  # Very small
    
    # Add entries that should exceed the limit
    cache.put("model", "text1", [0.1] * 10)  # First entry
    cache.put("model", "text2", [0.2] * 10)  # Second entry
    cache.put("model", "text3", [0.3] * 10)  # Should evict first
    
    # First entry should be evicted (FIFO)
    assert cache.get("model", "text1") is None
    assert cache.get("model", "text2") is not None
    assert cache.get("model", "text3") is not None


def test_index_persistence(temp_cache_dir):
    """Test that cache index persists across instances."""
    # Create first cache instance
    cache1 = EmbeddingCache.__new__(EmbeddingCache)
    cache1.max_size_bytes = 1024 * 1024
    cache1.cache_dir = temp_cache_dir
    cache1.index_file = temp_cache_dir / "index.json"
    cache1._load_index()
    
    embedding = [0.1, 0.2, 0.3]
    cache1.put("test-model", "persistent", embedding)
    
    # Create second cache instance
    cache2 = EmbeddingCache.__new__(EmbeddingCache)
    cache2.max_size_bytes = 1024 * 1024
    cache2.cache_dir = temp_cache_dir
    cache2.index_file = temp_cache_dir / "index.json"
    cache2._load_index()
    
    # Should be able to retrieve from second instance
    result = cache2.get("test-model", "persistent")
    assert result == embedding