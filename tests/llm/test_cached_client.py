"""
Tests for the cached LLM client functionality.
"""
import json
import os
from pathlib import Path

import pytest

from elroy.core.ctx import ElroyContext
from elroy.llm.cached_client import CachedLlmClient


def test_cached_llm_client_query_llm(cached_ctx: ElroyContext):
    """Test that the cached LLM client caches query_llm responses."""
    
    # Ensure we're using the cached client
    assert isinstance(cached_ctx.llm, CachedLlmClient)
    
    # Make a simple query
    prompt = "What is 2 + 2?"
    system = "You are a helpful math assistant."
    
    # First call - this should make a real API call and cache the result
    response1 = cached_ctx.llm.query_llm(prompt, system)
    assert response1  # Should have a response
    
    # Check that a cache file was created
    cache_dir = cached_ctx.llm.cache_dir
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) > 0, "No cache files were created"
    
    # Second call with same parameters - this should use the cached result
    response2 = cached_ctx.llm.query_llm(prompt, system)
    assert response2 == response1, "Cached response should be identical"
    
    # Verify cache file content
    cache_file = cache_files[0]
    with open(cache_file, 'r') as f:
        cached_data = json.load(f)
    
    assert "response" in cached_data
    assert cached_data["response"] == response1


def test_cached_llm_client_get_embedding(cached_ctx: ElroyContext):
    """Test that the cached LLM client caches embedding responses."""
    
    # Ensure we're using the cached client
    assert isinstance(cached_ctx.llm, CachedLlmClient)
    
    # Make an embedding request
    text = "Hello world"
    
    # First call - this should make a real API call and cache the result
    embedding1 = cached_ctx.llm.get_embedding(text)
    assert embedding1  # Should have an embedding
    assert isinstance(embedding1, list)
    assert len(embedding1) > 0
    
    # Check that a cache file was created
    cache_dir = cached_ctx.llm.cache_dir
    cache_files = list(cache_dir.glob("*.json"))
    
    # Find the embedding cache file
    embedding_cache_file = None
    for cache_file in cache_files:
        with open(cache_file, 'r') as f:
            cached_data = json.load(f)
        if "embedding" in cached_data:
            embedding_cache_file = cache_file
            break
    
    assert embedding_cache_file is not None, "No embedding cache file found"
    
    # Second call with same text - this should use the cached result
    embedding2 = cached_ctx.llm.get_embedding(text)
    assert embedding2 == embedding1, "Cached embedding should be identical"


def test_cached_llm_client_different_parameters(cached_ctx: ElroyContext):
    """Test that different parameters create different cache entries."""
    
    # Ensure we're using the cached client
    assert isinstance(cached_ctx.llm, CachedLlmClient)
    
    # Make two queries with different parameters
    response1 = cached_ctx.llm.query_llm("What is 2 + 2?", "You are a math assistant.")
    response2 = cached_ctx.llm.query_llm("What is 3 + 3?", "You are a math assistant.")
    
    # Different queries should potentially have different responses
    # (though we can't guarantee this in tests)
    
    # Check that separate cache files were created
    cache_dir = cached_ctx.llm.cache_dir
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) >= 2, "Should have at least 2 cache files for different queries"


def test_cache_directory_creation():
    """Test that the cache directory is created automatically."""
    
    # Test with a custom cache directory
    test_cache_dir = Path("/tmp/test_llm_cache")
    if test_cache_dir.exists():
        import shutil
        shutil.rmtree(test_cache_dir)
    
    # Create a cached client with custom directory
    from elroy.config.llm import get_chat_model, get_embedding_model
    
    chat_model = get_chat_model("gpt-4o-mini")
    embedding_model = get_embedding_model("text-embedding-3-small", 1536)
    
    client = CachedLlmClient(chat_model, embedding_model, cache_dir=test_cache_dir)
    
    # The directory should be created automatically
    assert test_cache_dir.exists()
    assert test_cache_dir.is_dir()
    
    # Clean up
    import shutil
    shutil.rmtree(test_cache_dir)


def test_cache_key_consistency():
    """Test that the same parameters always generate the same cache key."""
    
    from elroy.config.llm import get_chat_model, get_embedding_model
    
    chat_model = get_chat_model("gpt-4o-mini")
    embedding_model = get_embedding_model("text-embedding-3-small", 1536)
    
    client = CachedLlmClient(chat_model, embedding_model)
    
    # Generate cache keys for the same parameters multiple times
    key1 = client._get_cache_key("query_llm", prompt="Hello", system="You are helpful")
    key2 = client._get_cache_key("query_llm", prompt="Hello", system="You are helpful")
    
    assert key1 == key2, "Same parameters should generate the same cache key"
    
    # Different parameters should generate different keys
    key3 = client._get_cache_key("query_llm", prompt="Hi", system="You are helpful")
    
    assert key1 != key3, "Different parameters should generate different cache keys"