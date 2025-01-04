from dataclasses import dataclass
from importlib.resources import open_text
from typing import Optional

import yaml

from .constants import KNOWN_MODELS, Provider
from .paths import APP_NAME

with open_text(APP_NAME, "defaults.yml") as f:
    DEFAULTS_CONFIG = yaml.safe_load(f)


@dataclass
class ChatModel:
    name: str
    enable_caching: bool
    api_key: Optional[str]
    provider: Provider
    ensure_alternating_roles: (
        bool  # Whether to ensure that the first message is system message, and thereafter alternating between user and assistant.
    )
    api_base: Optional[str] = None
    organization: Optional[str] = None


def get_provider(model_name: str, api_base: Optional[str]) -> Provider:
    # check a hard coded dict to short circuit API calls to list models, if possible:

    for provider, models in KNOWN_MODELS.items():
        if model_name in models:
            return provider

    from .models import get_supported_openai_models

    if model_name in get_supported_openai_models():
        return Provider.OPENAI

    elif api_base:
        return Provider.OTHER

    from .models import get_supported_anthropic_models

    if model_name in get_supported_anthropic_models():
        return Provider.ANTHROPIC
    else:
        raise ValueError("Cannot determine provider for model")


@dataclass
class EmbeddingModel:
    model: str
    embedding_size: int
    enable_caching: bool
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    organization: Optional[str] = None


def get_chat_model(
    model_name: str,
    openai_api_key: Optional[str],
    anthropic_api_key: Optional[str],
    api_base: Optional[str],
    organization: Optional[str],
    enable_caching: bool,
) -> ChatModel:
    pass

    provider = get_provider(model_name, api_base)

    if provider == Provider.ANTHROPIC:
        assert anthropic_api_key is not None, "Anthropic API key is required for Anthropic chat models"
        ensure_alternating_roles = True
        api_key = anthropic_api_key
    elif provider == Provider.OPENAI:
        assert openai_api_key is not None, "OpenAI API key is required for OpenAI chat models"
        ensure_alternating_roles = False
        api_key = openai_api_key
    else:
        ensure_alternating_roles = False
        api_key = openai_api_key

    return ChatModel(
        name=model_name,
        api_key=api_key,
        ensure_alternating_roles=ensure_alternating_roles,
        api_base=api_base,
        organization=organization,
        enable_caching=enable_caching,
        provider=provider,
    )


def get_embedding_model(
    model_name: str, embedding_size: int, api_key: Optional[str], api_base: Optional[str], organization: Optional[str], enable_caching: bool
) -> EmbeddingModel:
    from litellm import open_ai_embedding_models

    if model_name in open_ai_embedding_models:
        assert api_key is not None, "OpenAI API key is required for OpenAI embedding models"

    return EmbeddingModel(
        model=model_name,
        embedding_size=embedding_size,
        api_key=api_key,
        api_base=api_base,
        organization=organization,
        enable_caching=enable_caching,
    )
