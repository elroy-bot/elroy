import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar
from dataclasses import asdict

from pydantic import BaseModel

from .client import LlmClient
from .stream_parser import StreamParser
from ..config.llm import ChatModel, EmbeddingModel
from ..repository.context_messages.data_models import ContextMessage


class CachedLlmClient(LlmClient):
    """
    LLM client that caches responses to JSON files for testing.
    
    This client extends the base LlmClient to add caching functionality
    for test environments. It will write responses to cache files and
    read from cache on subsequent requests with the same parameters.
    """
    
    def __init__(self, chat_model: ChatModel, embedding_model: EmbeddingModel, cache_dir: Optional[Path] = None):
        super().__init__(chat_model, embedding_model)
        
        # Default cache directory - tests/fixtures/llm_cache
        if cache_dir is None:
            # Find the project root by looking for pyproject.toml
            current_dir = Path(__file__).parent
            while current_dir.parent != current_dir:  # Stop at filesystem root
                if (current_dir / "pyproject.toml").exists():
                    self.cache_dir = current_dir / "tests" / "fixtures" / "llm_cache"
                    break
                current_dir = current_dir.parent
            else:
                # Fallback if we can't find project root
                self.cache_dir = Path.cwd() / "tests" / "fixtures" / "llm_cache"
        else:
            self.cache_dir = cache_dir
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, method_name: str, **kwargs) -> str:
        """Generate a cache key from method name and parameters."""
        # Create a stable hash from method name and kwargs
        cache_data = {
            "method": method_name,
            **kwargs
        }
        
        # Convert to JSON string with sorted keys for consistent hashing
        cache_str = json.dumps(cache_data, sort_keys=True, default=str)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def _get_cache_file(self, cache_key: str) -> Path:
        """Get the cache file path for a given cache key."""
        return self.cache_dir / f"{cache_key}.json"
    
    def _load_from_cache(self, cache_key: str) -> Optional[Any]:
        """Load a cached response if it exists."""
        cache_file = self._get_cache_file(cache_key)
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # If cache is corrupted, ignore it
                return None
        return None
    
    def _save_to_cache(self, cache_key: str, response: Any) -> None:
        """Save a response to cache."""
        cache_file = self._get_cache_file(cache_key)
        try:
            with open(cache_file, 'w') as f:
                json.dump(response, f, indent=2, default=str)
        except (IOError, TypeError) as e:
            # If we can't cache, just log and continue
            print(f"Warning: Could not cache LLM response: {e}")
    
    def generate_chat_completion_message(
        self,
        context_messages: List[ContextMessage],
        tool_schemas: List[Dict[str, Any]],
        enable_tools: bool = True,
        force_tool: Optional[str] = None,
    ) -> StreamParser:
        """Generate chat completion with caching for tests."""
        
        # Create cache key from inputs
        cache_key = self._get_cache_key(
            "generate_chat_completion_message",
            context_messages=[asdict(msg) for msg in context_messages],
            tool_schemas=tool_schemas,
            enable_tools=enable_tools,
            force_tool=force_tool,
            chat_model=self.chat_model.name,
        )
        
        # Try to load from cache first
        cached_response = self._load_from_cache(cache_key)
        if cached_response is not None:
            # Create a mock StreamParser from cached data
            from .mock_stream_parser import MockStreamParser
            return MockStreamParser(self.chat_model, cached_response)
        
        # If not in cache, call the real method
        stream_parser = super().generate_chat_completion_message(
            context_messages, tool_schemas, enable_tools, force_tool
        )
        
        # Cache the stream content as it's consumed
        # Note: We'll need to wrap the stream parser to cache its output
        return CachedStreamParser(stream_parser, cache_key, self._save_to_cache)
    
    def query_llm(self, prompt: str, system: str) -> str:
        """Query LLM with caching for tests."""
        cache_key = self._get_cache_key(
            "query_llm",
            prompt=prompt,
            system=system,
            chat_model=self.chat_model.name,
        )
        
        # Try to load from cache first
        cached_response = self._load_from_cache(cache_key)
        if cached_response is not None:
            return cached_response["response"]
        
        # If not in cache, call the real method
        response = super().query_llm(prompt, system)
        
        # Cache the response
        self._save_to_cache(cache_key, {"response": response})
        
        return response
    
    def query_llm_with_response_format(self, prompt: str, system: str, response_format: Type[BaseModel]) -> BaseModel:
        """Query LLM with response format and caching for tests."""
        cache_key = self._get_cache_key(
            "query_llm_with_response_format",
            prompt=prompt,
            system=system,
            response_format=response_format.__name__,
            chat_model=self.chat_model.name,
        )
        
        # Try to load from cache first
        cached_response = self._load_from_cache(cache_key)
        if cached_response is not None:
            return response_format.model_validate_json(cached_response["response"])
        
        # If not in cache, call the real method
        response = super().query_llm_with_response_format(prompt, system, response_format)
        
        # Cache the response (as JSON string)
        self._save_to_cache(cache_key, {"response": response.model_dump_json()})
        
        return response
    
    def query_llm_with_word_limit(self, prompt: str, system: str, word_limit: int) -> str:
        """Query LLM with word limit and caching for tests."""
        cache_key = self._get_cache_key(
            "query_llm_with_word_limit",
            prompt=prompt,
            system=system,
            word_limit=word_limit,
            chat_model=self.chat_model.name,
        )
        
        # Try to load from cache first
        cached_response = self._load_from_cache(cache_key)
        if cached_response is not None:
            return cached_response["response"]
        
        # If not in cache, call the real method
        response = super().query_llm_with_word_limit(prompt, system, word_limit)
        
        # Cache the response
        self._save_to_cache(cache_key, {"response": response})
        
        return response
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding with caching for tests."""
        cache_key = self._get_cache_key(
            "get_embedding",
            text=text,
            embedding_model=self.embedding_model.name,
        )
        
        # Try to load from cache first
        cached_response = self._load_from_cache(cache_key)
        if cached_response is not None:
            return cached_response["embedding"]
        
        # If not in cache, call the real method
        embedding = super().get_embedding(text)
        
        # Cache the embedding
        self._save_to_cache(cache_key, {"embedding": embedding})
        
        return embedding


class CachedStreamParser(StreamParser):
    """
    A wrapper around StreamParser that caches the stream content.
    """
    
    def __init__(self, stream_parser: StreamParser, cache_key: str, save_callback):
        self.stream_parser = stream_parser
        self.cache_key = cache_key
        self.save_callback = save_callback
        self._cached_content = []
        self._is_done = False
    
    def __getattr__(self, name):
        # Delegate all other attributes to the wrapped stream parser
        return getattr(self.stream_parser, name)
    
    def __iter__(self):
        return self
    
    def __next__(self):
        try:
            chunk = next(self.stream_parser)
            self._cached_content.append(chunk)
            return chunk
        except StopIteration:
            if not self._is_done:
                # Cache the complete stream when iteration is finished
                self._save_complete_response()
                self._is_done = True
            raise
    
    def _save_complete_response(self):
        """Save the complete stream response to cache."""
        try:
            # Get the final message content and tool calls
            final_content = getattr(self.stream_parser, 'message_content', '')
            tool_calls = getattr(self.stream_parser, 'tool_calls', [])
            
            cached_data = {
                "message_content": final_content,
                "tool_calls": tool_calls,
                "chunks": self._cached_content
            }
            
            self.save_callback(self.cache_key, cached_data)
        except Exception as e:
            print(f"Warning: Could not cache stream response: {e}")