import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from ..config.llm import ChatModel, EmbeddingModel
from ..core.logging import get_logger
from ..repository.context_messages.data_models import ContextMessage
from .client import LLMClient
from .stream_parser import StreamParser

logger = get_logger()

T = TypeVar("T", bound=BaseModel)


class CachedLLMClient(LLMClient):
    """Cached LLM client that saves responses to fixtures for testing."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize cached client with cache directory."""
        self.cache_dir = cache_dir or Path("tests/fixtures/llm_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_cache_key(self, **kwargs) -> str:
        """Generate cache key from request parameters."""
        # Create a deterministic hash from the request parameters
        cache_data = json.dumps(kwargs, sort_keys=True, default=str)
        return hashlib.sha256(cache_data.encode()).hexdigest()[:16]
    
    def _get_cache_path(self, cache_key: str, method: str) -> Path:
        """Get cache file path for a given key and method."""
        return self.cache_dir / f"{method}_{cache_key}.json"
    
    def _load_from_cache(self, cache_path: Path) -> Optional[Dict[str, Any]]:
        """Load cached response if it exists."""
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    cached_data = json.load(f)
                logger.info(f"Using cached LLM response from {cache_path}")
                return cached_data
            except Exception as e:
                logger.warning(f"Failed to load cache from {cache_path}: {e}")
        return None
    
    def _save_to_cache(self, cache_path: Path, request_data: Dict[str, Any], response: Any) -> None:
        """Save response to cache."""
        try:
            cache_data = {
                "request": request_data,
                "response": response
            }
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2, default=str)
            logger.info(f"Cached LLM response to {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to save cache to {cache_path}: {e}")
    
    def query_llm(self, model: ChatModel, prompt: str, system: str) -> str:
        """Query LLM with caching."""
        cache_key = self._get_cache_key(
            model=model.name,
            prompt=prompt,
            system=system,
            method="query_llm"
        )
        cache_path = self._get_cache_path(cache_key, "query_llm")
        
        # Try to load from cache
        cached_data = self._load_from_cache(cache_path)
        if cached_data:
            return cached_data["response"]
        
        # Cache miss - call real LLM
        response = super().query_llm(model, prompt, system)
        
        # Save to cache
        request_data = {
            "model": model.name,
            "prompt": prompt,
            "system": system,
            "method": "query_llm"
        }
        self._save_to_cache(cache_path, request_data, response)
        
        return response
    
    def query_llm_with_response_format(self, model: ChatModel, prompt: str, system: str, response_format: Type[T]) -> T:
        """Query LLM with response format and caching."""
        cache_key = self._get_cache_key(
            model=model.name,
            prompt=prompt,
            system=system,
            response_format=response_format.__name__,
            method="query_llm_with_response_format"
        )
        cache_path = self._get_cache_path(cache_key, "query_llm_with_response_format")
        
        # Try to load from cache
        cached_data = self._load_from_cache(cache_path)
        if cached_data:
            return response_format.model_validate(cached_data["response"])
        
        # Cache miss - call real LLM
        response = super().query_llm_with_response_format(model, prompt, system, response_format)
        
        # Save to cache (serialize the pydantic model)
        request_data = {
            "model": model.name,
            "prompt": prompt,
            "system": system,
            "response_format": response_format.__name__,
            "method": "query_llm_with_response_format"
        }
        self._save_to_cache(cache_path, request_data, response.model_dump())
        
        return response
    
    def query_llm_with_word_limit(self, model: ChatModel, prompt: str, system: str, word_limit: int) -> str:
        """Query LLM with word limit and caching."""
        cache_key = self._get_cache_key(
            model=model.name,
            prompt=prompt,
            system=system,
            word_limit=word_limit,
            method="query_llm_with_word_limit"
        )
        cache_path = self._get_cache_path(cache_key, "query_llm_with_word_limit")
        
        # Try to load from cache
        cached_data = self._load_from_cache(cache_path)
        if cached_data:
            return cached_data["response"]
        
        # Cache miss - call real LLM
        response = super().query_llm_with_word_limit(model, prompt, system, word_limit)
        
        # Save to cache
        request_data = {
            "model": model.name,
            "prompt": prompt,
            "system": system,
            "word_limit": word_limit,
            "method": "query_llm_with_word_limit"
        }
        self._save_to_cache(cache_path, request_data, response)
        
        return response
    
    def get_embedding(self, model: EmbeddingModel, text: str) -> List[float]:
        """Get embedding with caching."""
        cache_key = self._get_cache_key(
            model=model.name,
            text=text,
            method="get_embedding"
        )
        cache_path = self._get_cache_path(cache_key, "get_embedding")
        
        # Try to load from cache
        cached_data = self._load_from_cache(cache_path)
        if cached_data:
            return cached_data["response"]
        
        # Cache miss - call real LLM
        response = super().get_embedding(model, text)
        
        # Save to cache
        request_data = {
            "model": model.name,
            "text": text,
            "method": "get_embedding"
        }
        self._save_to_cache(cache_path, request_data, response)
        
        return response
    
    def generate_chat_completion_message(
        self,
        chat_model: ChatModel,
        context_messages: List[ContextMessage],
        tool_schemas: List[Dict[str, Any]],
        enable_tools: bool = True,
        force_tool: Optional[str] = None,
    ) -> StreamParser:
        """Generate chat completion with caching.
        
        Note: This method returns a StreamParser which is harder to cache directly.
        For now, we'll pass through to the parent implementation without caching.
        TODO: Implement caching for streaming responses if needed.
        """
        # For streaming responses, we'll skip caching for now
        # This could be enhanced later to cache the final accumulated response
        return super().generate_chat_completion_message(
            chat_model, context_messages, tool_schemas, enable_tools, force_tool
        )