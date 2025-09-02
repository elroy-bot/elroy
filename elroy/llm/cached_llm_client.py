"""
Cached LLM Client for Tests Only.

WARNING: This client is ONLY intended for use in tests to cache LLM responses
to disk for reproducible test runs and cost savings. It should NEVER be used
in production code as it would create unwanted caching behavior.

The caching mechanism writes responses to JSON files in tests/fixtures/llm_cache/
which can be checked into version control so remote test runs use cached data
instead of making real API calls.
"""
import hashlib
import json
import os
from pathlib import Path
from typing import List, Type, TypeVar, Any, Dict
from pydantic import BaseModel
from ..config.llm import ChatModel, EmbeddingModel
from .llm_client import LLMClient

T = TypeVar("T", bound=BaseModel)


class CachedLLMClient(LLMClient):
    """
    TEST-ONLY LLM client that caches responses to disk.
    
    ⚠️  WARNING: This client is ONLY for tests! It caches all LLM responses
    to disk files in tests/fixtures/llm_cache/. This is useful for:
    
    1. Making tests deterministic and reproducible
    2. Reducing API costs during test development 
    3. Enabling offline test execution
    4. Consistent CI/CD test runs
    
    NEVER use this client in production - it would cache all LLM interactions
    to disk which is not desired behavior for a production application.
    
    Cache files are organized by content hash to ensure deterministic behavior
    regardless of when the test is run.
    """
    
    def __init__(self, cache_dir: str = "tests/fixtures/llm_cache"):
        """
        Initialize the cached LLM client.
        
        Args:
            cache_dir: Directory to store cache files (relative to project root)
        """
        # This is TEST-ONLY - we assume we're running from project root during tests
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, data: Dict[str, Any]) -> str:
        """
        Generate a deterministic cache key based on input parameters.
        
        Uses content-based hashing to ensure the same inputs always produce
        the same cache key, making tests reproducible.
        """
        # Create a sorted, stable representation of the input data
        cache_data = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(cache_data.encode()).hexdigest()
    
    def _get_cache_path(self, method: str, cache_key: str) -> Path:
        """Get the file path for a cached response."""
        return self.cache_dir / f"{method}_{cache_key}.json"
    
    def _load_from_cache(self, cache_path: Path) -> Any:
        """Load a response from cache file."""
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                # If cache file is corrupted, ignore it and re-generate
                pass
        return None
    
    def _save_to_cache(self, cache_path: Path, data: Any) -> None:
        """Save a response to cache file."""
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            # If we can't save to cache, log but don't fail the test
            print(f"Warning: Could not save to cache {cache_path}: {e}")
    
    def query_llm(self, model: ChatModel, prompt: str, system: str) -> str:
        """
        Query LLM with caching for tests.
        
        Caches based on model name, prompt, and system message content.
        Falls back to real API call if cache miss, then saves response.
        """
        cache_data = {
            "method": "query_llm",
            "model": model.name,
            "prompt": prompt,
            "system": system
        }
        
        cache_key = self._get_cache_key(cache_data)
        cache_path = self._get_cache_path("query_llm", cache_key)
        
        # Try to load from cache first
        cached_response = self._load_from_cache(cache_path)
        if cached_response is not None:
            return cached_response["response"]
        
        # Cache miss - make real API call
        response = super().query_llm(model=model, prompt=prompt, system=system)
        
        # Save to cache for future test runs
        self._save_to_cache(cache_path, {"response": response})
        
        return response
    
    def query_llm_with_response_format(self, model: ChatModel, prompt: str, system: str, response_format: Type[T]) -> T:
        """
        Query LLM with response format, using caching for tests.
        
        Caches based on model, prompt, system message, and response format class name.
        """
        cache_data = {
            "method": "query_llm_with_response_format",
            "model": model.name,
            "prompt": prompt,
            "system": system,
            "response_format": response_format.__name__
        }
        
        cache_key = self._get_cache_key(cache_data)
        cache_path = self._get_cache_path("query_llm_with_response_format", cache_key)
        
        # Try to load from cache first
        cached_response = self._load_from_cache(cache_path)
        if cached_response is not None:
            # Reconstruct the Pydantic model from cached JSON
            return response_format.model_validate(cached_response["response"])
        
        # Cache miss - make real API call
        response = super().query_llm_with_response_format(
            model=model, prompt=prompt, system=system, response_format=response_format
        )
        
        # Save to cache for future test runs
        self._save_to_cache(cache_path, {"response": response.model_dump()})
        
        return response
    
    def query_llm_with_word_limit(self, model: ChatModel, prompt: str, system: str, word_limit: int) -> str:
        """
        Query LLM with word limit, using caching for tests.
        
        Caches based on model, prompt, system message, and word limit.
        """
        cache_data = {
            "method": "query_llm_with_word_limit",
            "model": model.name,
            "prompt": prompt,
            "system": system,
            "word_limit": word_limit
        }
        
        cache_key = self._get_cache_key(cache_data)
        cache_path = self._get_cache_path("query_llm_with_word_limit", cache_key)
        
        # Try to load from cache first
        cached_response = self._load_from_cache(cache_path)
        if cached_response is not None:
            return cached_response["response"]
        
        # Cache miss - make real API call
        response = super().query_llm_with_word_limit(
            model=model, prompt=prompt, system=system, word_limit=word_limit
        )
        
        # Save to cache for future test runs
        self._save_to_cache(cache_path, {"response": response})
        
        return response
    
    def get_embedding(self, model: EmbeddingModel, text: str) -> List[float]:
        """
        Get embedding with caching for tests.
        
        Caches based on model name and text content.
        """
        cache_data = {
            "method": "get_embedding",
            "model": model.name,
            "text": text
        }
        
        cache_key = self._get_cache_key(cache_data)
        cache_path = self._get_cache_path("get_embedding", cache_key)
        
        # Try to load from cache first
        cached_response = self._load_from_cache(cache_path)
        if cached_response is not None:
            return cached_response["response"]
        
        # Cache miss - make real API call
        response = super().get_embedding(model=model, text=text)
        
        # Save to cache for future test runs
        self._save_to_cache(cache_path, {"response": response})
        
        return response