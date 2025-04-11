"""
OpenAI-compatible API for Elroy.

This module provides an OpenAI-compatible API that augments chat completion
requests with memories from Elroy.
"""

from .litellm_provider import ElroyLiteLLMProvider
from .server import app, run_server

__all__ = ["ElroyLiteLLMProvider", "app", "run_server"]
