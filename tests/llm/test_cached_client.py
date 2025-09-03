import json

from elroy.core.ctx import ElroyContext
from elroy.llm.cached_client import CachedLLMClient


def test_cached_client_caches_responses(ctx: ElroyContext, tmp_path):
    """Test that the cached client properly caches LLM responses."""

    # Create a fresh cached client with a specific cache directory
    cache_dir = tmp_path / "test_cache"
    cached_client = CachedLLMClient(cache_dir)

    # First call - should hit the API and cache the response
    response1 = cached_client.query_llm(
        model=ctx.chat_model,
        system="This is a test. Respond with exactly: 'Cached test response'",
        prompt="Test prompt",
    )

    # Verify cache directory was created
    assert cache_dir.exists()

    # Check that cache files were created
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 1

    # Verify cache file contents
    cache_file = cache_files[0]
    with open(cache_file, "r") as f:
        cache_data = json.load(f)

    assert "request" in cache_data
    assert "response" in cache_data
    assert cache_data["request"]["method"] == "query_llm"
    assert cache_data["request"]["system"] == "This is a test. Respond with exactly: 'Cached test response'"
    assert cache_data["request"]["prompt"] == "Test prompt"

    # Second call - should use cached response
    response2 = cached_client.query_llm(
        model=ctx.chat_model,
        system="This is a test. Respond with exactly: 'Cached test response'",
        prompt="Test prompt",
    )

    # Responses should be identical
    assert response1 == response2

    # Cache directory should still have only one file (no new API call)
    cache_files_after = list(cache_dir.glob("*.json"))
    assert len(cache_files_after) == 1


def test_cached_client_different_prompts_create_different_cache_files(ctx: ElroyContext, tmp_path):
    """Test that different prompts create separate cache entries."""

    cache_dir = tmp_path / "test_cache"
    cached_client = CachedLLMClient(cache_dir)

    # Call with first prompt
    response1 = cached_client.query_llm(
        model=ctx.chat_model,
        system="Test system",
        prompt="First prompt",
    )

    # Call with second prompt
    response2 = cached_client.query_llm(
        model=ctx.chat_model,
        system="Test system",
        prompt="Second prompt",
    )

    # Should have two different cache files
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 2

    # Responses should be different
    assert response1 != response2


def test_cached_client_integration_with_context(ctx: ElroyContext):
    """Test that the context uses cached client in tests."""

    # The ctx fixture should already be configured with a cached client
    # Verify it's actually a CachedLLMClient instance
    assert isinstance(ctx.llm_client, CachedLLMClient)

    # Test that it works
    response = ctx.llm_client.query_llm(
        model=ctx.chat_model,
        system="This is a test. Respond with: 'Integration test successful'",
        prompt="Test integration",
    )

    assert "integration" in response.lower() or "successful" in response.lower()
