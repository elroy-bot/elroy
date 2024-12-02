import re
from dataclasses import dataclass
from typing import Callable, List

from toolz import last, pipe
from toolz.curried import filter


@dataclass
class ModelAlias:
    keyword: str
    description: str
    resolver: Callable[[], str]


CHAT_MODEL_ALIASES = {
    "sonnet": ModelAlias("sonnet", "Anthropic's Sonnet model", lambda: resolve_anthropic("sonnet")),
    "opus": ModelAlias("opus", "Anthropic's Opus model", lambda: resolve_anthropic("opus")),
    "4o": ModelAlias("gpt4o", "OpenAI's GPT-4o model", lambda: resolve_openai(r"^gpt-4o(?!-mini).*")),
    "4o-mini": ModelAlias("gpt4o-mini", "OpenAI's GPT-4o-mini model", lambda: resolve_openai(r"gpt-4o-mini")),
    "o1": ModelAlias("o1", "OpenAI's o1 model", lambda: resolve_openai(r"^o1(?:-preview)?(?:-\d{4})?")),
    "o1-mini": ModelAlias("o1-mini", "OpenAI's o1-mini model", lambda: resolve_openai(r"o1-mini")),
}


def resolve_openai(pattern: str) -> str:
    from litellm import open_ai_chat_completion_models

    return _get_model_alias(pattern, open_ai_chat_completion_models)


def resolve_anthropic(pattern: str) -> str:
    from litellm import anthropic_models

    return _get_model_alias(pattern, anthropic_models)


def _get_model_alias(pattern: str, models: List[str]) -> str:
    """
    Get the highest sorted model name that matches the regex pattern.

    Args:
        pattern: Regex pattern to match against model names
        models: List of model name strings

    Returns:
        The highest sorted matching model name
    """
    return pipe(
        models,
        filter(lambda x: re.search(pattern, x, re.IGNORECASE)),
        sorted,
        last,
    )  # type: ignore
