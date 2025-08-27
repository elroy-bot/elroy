# Cached LLM Client for Tests

This implementation provides a cached LLM client specifically for testing purposes. The client caches LLM responses to local files, allowing tests to run consistently without making repeated API calls.

## Overview

The cached client architecture includes:

- **`LLMClient`**: Base class that wraps existing LLM functions in a clean interface
- **`CachedLLMClient`**: Subclass that adds caching functionality for tests
- **Test Integration**: Automatic setup in test fixtures to use cached responses

## How It Works

### Caching Mechanism

1. **Cache Key Generation**: The client generates deterministic cache keys based on request parameters (model, prompt, system message, etc.)
2. **Cache Storage**: Responses are saved as JSON files in `tests/fixtures/llm_cache/`
3. **Cache Lookup**: On subsequent calls with identical parameters, cached responses are returned instead of making API calls
4. **Fallback**: If no cache exists, the client makes a real API call and saves the response

### Cache File Format

Cache files are named using the pattern: `{method}_{cache_key}.json`

```json
{
  "request": {
    "model": "gpt-5-nano",
    "prompt": "Hello world",
    "system": "You are a helpful assistant",
    "method": "query_llm"
  },
  "response": "Hello! How can I assist you today?"
}
```

## Usage

### In Production Code

Use the ElroyContext's `llm_client` property instead of calling LLM functions directly:

```python
# Instead of:
from elroy.llm.client import query_llm
response = query_llm(model=ctx.chat_model, prompt="Hello", system="You are helpful")

# Use:
response = ctx.llm_client.query_llm(model=ctx.chat_model, prompt="Hello", system="You are helpful")
```

### In Tests

The test fixtures automatically configure the ElroyContext to use a `CachedLLMClient`:

```python
def test_my_feature(ctx: ElroyContext):
    # This will use cached responses in tests
    response = ctx.llm_client.query_llm(
        model=ctx.chat_model,
        prompt="Test prompt",
        system="Test system"
    )
    assert "expected" in response.lower()
```

### Supported Methods

The cached client supports all LLM operations:

- `query_llm(model, prompt, system)` - Basic LLM query
- `query_llm_with_response_format(model, prompt, system, response_format)` - Structured responses
- `query_llm_with_word_limit(model, prompt, system, word_limit)` - Word-limited responses
- `get_embedding(model, text)` - Text embeddings
- `generate_chat_completion_message(...)` - Chat completions (streaming not cached)

## Benefits

### For Development
- **Consistent Results**: Tests produce deterministic outputs
- **Faster Tests**: No network calls after initial cache population
- **Cost Savings**: Reduces API usage in testing
- **Offline Testing**: Tests can run without internet connectivity

### For Production
- **Zero Impact**: Production code is unaffected by test caching
- **Clean Architecture**: Separation of concerns with clear interfaces
- **Backward Compatibility**: Existing function calls still work

## Cache Management

### Manual Cache Creation

To populate cache for new tests:

1. Run tests normally - they will make API calls and save responses
2. Review cached responses for accuracy
3. Commit cache files to version control for team sharing

### Cache Directory Structure

```
tests/
├── fixtures/
│   ├── llm_cache/              # LLM response cache
│   │   ├── query_llm_abc123.json
│   │   ├── get_embedding_def456.json
│   │   └── ...
│   └── other_fixtures...
```

### Cache Validation

Use the validation script to verify the implementation:

```bash
python validate_cached_client.py
```

## Implementation Details

### Thread Safety
The current implementation is not thread-safe. For concurrent tests, consider using separate cache directories per test.

### Cache Invalidation
Cache keys are generated from all request parameters. Any change in parameters (model, prompt, system message) creates a new cache entry.

### Performance
- Cache lookups are fast (simple file reads)
- Cache key generation uses SHA-256 hashing for uniqueness
- JSON serialization handles complex response formats

## Future Enhancements

Potential improvements:

1. **Streaming Response Caching**: Currently `generate_chat_completion_message` is not cached
2. **Cache Expiration**: Time-based cache invalidation
3. **Compression**: Compress large cache files
4. **Cache Statistics**: Track hit/miss ratios
5. **Selective Caching**: Configuration for which methods to cache