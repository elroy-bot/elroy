import os
from dataclasses import dataclass
from importlib.resources import open_text
from typing import Optional

import yaml

from .constants import (
    CLAUDE_3_5_SONNET,
    GEMINI_2_0_FLASH,
    GEMINI_PREFIX,
    GPT_4O,
    KNOWN_MODELS,
    TEXT_EMBEDDING_3_SMALL,
    Provider,
)
from .paths import APP_NAME

with open_text(APP_NAME, "defaults.yml") as f:
    DEFAULTS_CONFIG = yaml.safe_load(f)


@dataclass
class ChatModel:
    name: str
    enable_caching: bool
    api_key: Optional[str]
    provider: Provider
    inline_tool_calls: bool
    ensure_alternating_roles: (
        bool  # Whether to ensure that the first message is system message, and thereafter alternating between user and assistant.
    )
    api_base: Optional[str] = None


def get_provider(model_name: str, api_base: Optional[str]) -> Provider:
    # check a hard coded dict to short circuit API calls to list models, if possible:

    for provider, models in KNOWN_MODELS.items():
        if model_name in models:
            return provider
    if model_name.startswith(GEMINI_PREFIX):
        return Provider.GEMINI
    elif api_base:
        return Provider.OTHER
    else:
        raise ValueError("Cannot determine provider for model")


@dataclass
class EmbeddingModel:
    name: str
    embedding_size: int
    enable_caching: bool
    api_key: Optional[str] = None
    api_base: Optional[str] = None


def infer_chat_model_name() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return CLAUDE_3_5_SONNET
    elif os.environ.get("OPENAI_API_KEY"):
        return GPT_4O
    elif os.environ.get("GEMINI_API_KEY"):
        return GEMINI_2_0_FLASH
    else:
        raise ValueError(
            "Could not infer chat model. Please set chat model, or provide API keys. See: https://github.com/elroy-bot/elroy/blob/main/docs/configuration.md"
        )


def infer_embedding_model_name() -> str:
    if os.environ.get("OPENAI_API_KEY"):
        return TEXT_EMBEDDING_3_SMALL
    # elif os.environ.get("GEMINI_API_KEY"): # TODO: figure out how to support different embedding sizes
    # return GEMINI_TEXT_EMBEDDING_004
    else:
        raise ValueError(
            "Could not infer embedding model. Please set embedding model, or provide API keys. See: https://github.com/elroy-bot/elroy/blob/main/docs/configuration.md"
        )


def get_chat_model(
    model_name: str,
    api_key: Optional[str],  # recommended key to pass in
    api_base: Optional[str],  # recommended base to pass in
    openai_api_key: Optional[str],  # supported for backwards compatibility
    openai_api_base: Optional[str],  # supported for backwards compatibility
    enable_caching: bool,
    inline_tool_calls: bool,
) -> ChatModel:

    provider = get_provider(model_name, api_base)

    if provider == Provider.ANTHROPIC:
        ensure_alternating_roles = True
    elif provider == Provider.OTHER:
        ensure_alternating_roles = False
        api_key = api_key or openai_api_key
        api_base = api_base or openai_api_base
    else:
        ensure_alternating_roles = False

    return ChatModel(
        name=model_name,
        api_key=api_key,
        ensure_alternating_roles=ensure_alternating_roles,
        inline_tool_calls=inline_tool_calls,
        api_base=api_base,
        enable_caching=enable_caching,
        provider=provider,
    )


def get_embedding_model(
    model_name: str,
    embedding_size: int,
    api_key: Optional[str],  # recommended key to pass in
    api_base: Optional[str],  # recommended base to pass in
    openai_api_key: Optional[str],  # supported for backwards compatibility
    openai_api_base: Optional[str],  # supported for backwards compatibility
    openai_embedding_api_base: Optional[str],  # supported for backwards compatibility
    chat_api_key: Optional[str],  # supported in case embedding model is from same provider as chat model
    chat_api_base: Optional[str],  # supported in case embedding model is from same provider as chat model
    enable_caching: bool,
) -> EmbeddingModel:
    return EmbeddingModel(
        name=model_name,
        embedding_size=embedding_size,
        api_key=api_key or chat_api_key or openai_api_key,
        api_base=api_base or openai_embedding_api_base or chat_api_base or openai_api_base,
        enable_caching=enable_caching,
    )
