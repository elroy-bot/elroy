"""
Base LLM Client class that wraps existing LLM functions for class-based interface.
"""
from typing import List, Type, TypeVar
from pydantic import BaseModel
from ..config.llm import ChatModel, EmbeddingModel
from .client import query_llm, query_llm_with_response_format, query_llm_with_word_limit, get_embedding

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    Base class that provides a class-based interface to LLM functions.
    
    This wraps the existing standalone LLM functions to provide a consistent
    interface that can be easily extended or mocked in tests.
    """
    
    def query_llm(self, model: ChatModel, prompt: str, system: str) -> str:
        """Query the LLM with a prompt and system message."""
        return query_llm(model=model, prompt=prompt, system=system)
    
    def query_llm_with_response_format(self, model: ChatModel, prompt: str, system: str, response_format: Type[T]) -> T:
        """Query the LLM with a specific response format."""
        return query_llm_with_response_format(
            model=model, 
            prompt=prompt, 
            system=system, 
            response_format=response_format
        )
    
    def query_llm_with_word_limit(self, model: ChatModel, prompt: str, system: str, word_limit: int) -> str:
        """Query the LLM with a word limit constraint."""
        return query_llm_with_word_limit(
            model=model, 
            prompt=prompt, 
            system=system, 
            word_limit=word_limit
        )
    
    def get_embedding(self, model: EmbeddingModel, text: str) -> List[float]:
        """Generate an embedding for the given text."""
        return get_embedding(model=model, text=text)