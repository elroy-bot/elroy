# LLM Cache Directory

This directory contains cached LLM responses for test execution.

## Purpose

The cached LLM client (`CachedLlmClient`) stores responses from LLM API calls in JSON files within this directory. This allows tests to:

1. **Run offline**: Tests can run without making actual API calls to LLM providers
2. **Be deterministic**: Same inputs always produce the same outputs
3. **Be fast**: No network latency from API calls
4. **Work in CI/CD**: Remote test runs can use cached responses instead of requiring API keys

## How it works

1. When a test uses the `cached_ctx` fixture, it gets an `ElroyContext` with a `CachedLlmClient`
2. The cached client checks for existing cache files based on a hash of the request parameters
3. If a cache file exists, it returns the cached response
4. If no cache exists, it makes the real API call and saves the response to a new cache file

## Cache Files

Cache files are named using MD5 hashes of the request parameters and have the `.json` extension. Each file contains:

- The complete response data for the specific request
- Metadata about the request (method name, parameters)

## Version Control

These cache files **can** be committed to version control to enable offline testing on CI/CD systems. The cache files are deterministic and safe to share across different environments.

## Manual Cache Management

To clear the cache (force fresh API calls in tests):
```bash
rm tests/fixtures/llm_cache/*.json
```

To selectively clear cache for specific operations, examine the cache files and remove the relevant ones.