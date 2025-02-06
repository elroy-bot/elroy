import re
from functools import partial
from typing import List, Optional, Tuple

from toolz import assoc, first, pipe
from toolz.curried import filter

from .constants import KNOWN_MODELS, Provider
from .llm import ChatModel, EmbeddingModel


def resolve_chat_model_config(**kwargs) -> ChatModel:
    model_name = resolve_model_alias(kwargs["chat_model"])
    if "claude" in model_name:
        kwargs.get("chat_model_api_key") or kwargs.get("anthropic_api_key")
        Provider.ANTHROPIC
    else:
        kwargs.get("chat_model_api_key") or kwargs.get("openai_api_key")

    kwargs.get("chat_model_base_url") or kwargs.get("openai_api_base")


def resolve_anthropic(pattern: str) -> str:
    return pipe(
        get_supported_anthropic_models(),
        filter(lambda x: re.search(pattern, x, re.IGNORECASE)),
        first,
    )  # type: ignore


def get_supported_openai_models() -> List[str]:
    from litellm import open_ai_chat_completion_models

    # Returns supported chat models, in order of power

    def _model_sort(model_name: str) -> Tuple[int, int, int, int]:
        """
        Returns a numeric score representing the relative power of a model.
        Higher scores indicate more powerful models.
        """
        # Base score based on model family
        if model_name.startswith("o1"):
            score = 1000
        elif "gpt-4o" in model_name:
            score = 500
        elif "gpt-4" in model_name:
            score = 100
        elif "gpt-3.5" in model_name:
            score = 50
        else:
            score = 0

        # Adjustments for specific variants
        if "turbo" in model_name:
            modifier = 10
        elif "preview" in model_name:
            modifier = -1
        elif "mini" in model_name:
            modifier = -5
        else:
            modifier = 0

        # Version number adjustment (e.g., 0125 in gpt-4-0125-preview)
        version_match = re.search(r"-(\d{4})$", model_name)
        if version_match:
            version_num = int(version_match.group(1))
        else:
            version_num = 0

        date_match = re.search(r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])", model_name)
        if date_match:
            date_int = int(date_match.group(0).replace("-", ""))
        else:
            # no date string will means e.g. gpt-4o, which will be the most recent model. Thus missing date = more powerful.
            date_int = 99999999

        return (score, modifier, version_num, date_int)

    return pipe(
        sorted(open_ai_chat_completion_models, key=_model_sort, reverse=True),
        filter(partial(re.search, r"^gpt-\d|^o1")),
        filter(lambda x: "vision" not in x),
        filter(lambda x: "audio" not in x),
        list,
    )


# This may result in API calls!
def get_supported_anthropic_models() -> List[str]:
    from litellm import anthropic_models

    def _model_sort(model_name: str) -> Tuple[int, float, int]:
        """
        Returns a numeric score representing the relative power of an Anthropic model.
        Higher scores indicate more powerful models.
        """

        version_match = re.search(r"claude-(?:instant-)?(\d+)(?:\.(\d+))?", model_name)
        if version_match:
            major = int(version_match.group(1))
            minor = int(version_match.group(2)) if version_match.group(2) else 0
            version = float(f"{major}.{minor}")
        else:
            version = 0.0

        date_match = re.search(r"(\d{8})", model_name)
        date = int(date_match.group(1)) if date_match else 0

        # Base score based on major version and subversion
        if "opus" in model_name:
            score = 350
        elif "sonnet" in model_name:
            score = 300
        elif "haiku" in model_name:
            score = 200
        elif "claude1" in model_name:
            score = 100
        elif "instant" in model_name:
            score = -50
        else:
            score = 0

        return (score, version, date)

    return sorted(anthropic_models, key=_model_sort, reverse=True)


def get_fallback_model(chat_model: ChatModel) -> Optional[ChatModel]:
    openai_models = get_supported_openai_models()
    anthropic_models = get_supported_anthropic_models()

    if chat_model.name in openai_models:
        model_list = openai_models
    elif chat_model.name in anthropic_models:
        model_list = anthropic_models
    else:
        return None

    idx = model_list.index(chat_model.name) + 1
    if idx > len(model_list) - 1:
        return None

    name = model_list[idx]

    # duplicate all settings, asside from the name
    return pipe(
        chat_model.__dict__,
        lambda x: assoc(x, "name", name),
        lambda x: ChatModel(**x),
    )  # type: ignore


def resolve_model_alias(model_name: str) -> str:
    if model_name in ["sonnet", "opus", "haiku"]:
        return resolve_anthropic(model_name)
    else:
        return {
            "gpt4o": "gpt-4o",
            "gpt4o_mini": "gpt-4o-mini",
            "o1": "o1",
            "o1_mini": "o1-mini",
        }.get(model_name, model_name)


def get_provider(model_name: str, api_base: Optional[str]) -> Provider:
    # check a hard coded dict to short circuit API calls to list models, if possible:

    for provider, models in KNOWN_MODELS.items():
        if model_name in models:
            return provider

    from .model_config import get_supported_openai_models

    if model_name in get_supported_openai_models():
        return Provider.OPENAI

    elif api_base:
        return Provider.OTHER

    from .model_config import get_supported_anthropic_models

    if model_name in get_supported_anthropic_models():
        return Provider.ANTHROPIC
    else:
        raise ValueError("Cannot determine provider for model")


def get_chat_model(
    model_name: str,
    openai_api_key: Optional[str],
    anthropic_api_key: Optional[str],
    api_base: Optional[str],
    organization: Optional[str],
    enable_caching: bool,
    inline_tool_calls: bool,
) -> ChatModel:

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
        inline_tool_calls=inline_tool_calls,
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
        name=model_name,
        embedding_size=embedding_size,
        api_key=api_key,
        api_base=api_base,
        organization=organization,
        enable_caching=enable_caching,
    )
