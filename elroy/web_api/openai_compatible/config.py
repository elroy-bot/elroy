"""
Configuration for the OpenAI-compatible API server.

This module handles loading configuration from environment variables and provides
default values for various settings.
"""

import os
from typing import List

from pydantic import BaseModel, Field


class OpenAIServerConfig(BaseModel):
    """Configuration for the OpenAI-compatible API server."""

    port: int = Field(
        default=int(os.environ.get("PORT", "8000")),
        description="Port to run the server on",
    )
    host: str = Field(
        default=os.environ.get("HOST", "127.0.0.1"),
        description="Host to bind to",
    )
    enable_auth: bool = Field(
        default=os.environ.get("ENABLE_AUTH", "false").lower() == "true",
        description="Whether to enable API key authentication",
    )
    api_keys: List[str] = Field(
        default_factory=lambda: [key.strip() for key in os.environ.get("API_KEYS", "").split(",") if key.strip()],
        description="Comma-separated list of valid API keys (used only when ENABLE_AUTH is true)",
    )
    enable_memory_creation: bool = Field(
        default=os.environ.get("ENABLE_MEMORY_CREATION", "true").lower() == "true",
        description="Whether to create memories from conversations",
    )
    memory_creation_interval: int = Field(
        default=int(os.environ.get("MEMORY_CREATION_INTERVAL", "10")),
        description="How often to create memories (in number of messages)",
    )
    max_memories_per_request: int = Field(
        default=int(os.environ.get("MAX_MEMORIES_PER_REQUEST", "5")),
        description="Maximum number of memories to include in a request",
    )
    relevance_threshold: float = Field(
        default=float(os.environ.get("RELEVANCE_THRESHOLD", "0.7")),
        description="Threshold for memory relevance",
    )

    @classmethod
    def from_env(cls) -> "OpenAIServerConfig":
        """Create a configuration object from environment variables."""
        return cls(
            port=int(os.environ.get("PORT", "8000")),
            host=os.environ.get("HOST", "127.0.0.1"),
            enable_auth=os.environ.get("ENABLE_AUTH", "false").lower() == "true",
            api_keys=[key.strip() for key in os.environ.get("API_KEYS", "").split(",") if key.strip()],
            enable_memory_creation=os.environ.get("ENABLE_MEMORY_CREATION", "true").lower() == "true",
            memory_creation_interval=int(os.environ.get("MEMORY_CREATION_INTERVAL", "10")),
            max_memories_per_request=int(os.environ.get("MAX_MEMORIES_PER_REQUEST", "5")),
            relevance_threshold=float(os.environ.get("RELEVANCE_THRESHOLD", "0.7")),
        )


def get_config() -> OpenAIServerConfig:
    """Get the server configuration from environment variables."""
    return OpenAIServerConfig.from_env()
