import hashlib
import json
import os
from pathlib import Path
from typing import List, Type, TypeVar

from pydantic import BaseModel

from .client import LLMClient

T = TypeVar("T", bound=BaseModel)


class CachedLLMClient(LLMClient):
    """LLM client that caches responses to disk for test reproducibility."""
    
    def __init__(self, chat_model, embedding_model, cache_dir: Path = None):
        super().__init__(chat_model, embedding_model)
        
        if cache_dir is None:
            # Default to tests/fixtures/llm_cache
            base_dir = Path(__file__).parent.parent.parent
            cache_dir = base_dir / "tests" / "fixtures" / "llm_cache"
        
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, method: str, **kwargs) -> str:
        """Generate a deterministic cache key based on method and parameters."""
        cache_data = {
            "method": method,
            "chat_model": self.chat_model.name if hasattr(self.chat_model, 'name') else str(self.chat_model),
            "embedding_model": self.embedding_model.name if hasattr(self.embedding_model, 'name') else str(self.embedding_model),
            **kwargs
        }
        
        # Sort to ensure consistent hashing
        cache_json = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_json.encode()).hexdigest()[:16]
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the cache file path for a given cache key."""
        return self.cache_dir / f"{cache_key}.json"
    
    def _load_from_cache(self, cache_key: str):
        """Load a cached response if it exists."""
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # If cache is corrupted, remove it
                cache_path.unlink()
        return None
    
    def _save_to_cache(self, cache_key: str, response):
        """Save a response to the cache."""
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, 'w') as f:
                json.dump(response, f, indent=2)
        except IOError:
            # If we can't write to cache, just continue without caching
            pass
    
    def query_llm(self, prompt: str, system: str) -> str:
        """Query the LLM with caching."""
        cache_key = self._get_cache_key("query_llm", prompt=prompt, system=system)
        
        # Try to load from cache
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return cached["response"]
        
        # Fall back to real API call
        response = super().query_llm(prompt, system)
        
        # Save to cache
        self._save_to_cache(cache_key, {"response": response})
        
        return response
    
    def query_llm_with_response_format(self, prompt: str, system: str, response_format: Type[T]) -> T:
        """Query the LLM with structured response format and caching."""
        cache_key = self._get_cache_key(
            "query_llm_with_response_format",
            prompt=prompt,
            system=system,
            response_format=response_format.__name__
        )
        
        # Try to load from cache
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return response_format.model_validate(cached["response"])
        
        # Fall back to real API call
        response = super().query_llm_with_response_format(prompt, system, response_format)
        
        # Save to cache (serialize the pydantic model)
        self._save_to_cache(cache_key, {"response": response.model_dump()})
        
        return response
    
    def query_llm_with_word_limit(self, prompt: str, system: str, word_limit: int) -> str:
        """Query the LLM with word limit and caching."""
        cache_key = self._get_cache_key(
            "query_llm_with_word_limit",
            prompt=prompt,
            system=system,
            word_limit=word_limit
        )
        
        # Try to load from cache
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return cached["response"]
        
        # Fall back to real API call
        response = super().query_llm_with_word_limit(prompt, system, word_limit)
        
        # Save to cache
        self._save_to_cache(cache_key, {"response": response})
        
        return response
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding with caching."""
        cache_key = self._get_cache_key("get_embedding", text=text)
        
        # Try to load from cache
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return cached["embedding"]
        
        # Fall back to real API call
        embedding = super().get_embedding(text)
        
        # Save to cache
        self._save_to_cache(cache_key, {"embedding": embedding})
        
        return embedding