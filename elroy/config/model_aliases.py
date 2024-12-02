import re
from typing import List

from toolz import last, pipe
from toolz.curried import filter


def get_sonnet() -> str:

    from litellm import anthropic_models

    return _get_model_alias("sonnet", anthropic_models)


def get_opus() -> str:

    from litellm import anthropic_models

    return _get_model_alias("opus", anthropic_models)


def get_gpt4o() -> str:
    """Get the latest GPT-4o model."""
    from litellm import openai_models

    return _get_model_alias(r"^gpt-4o(?!-mini).*", openai_models)


def get_gpt4o_mini() -> str:
    """Get the latest GPT-4o-mini model."""
    from litellm import openai_models

    return _get_model_alias(r"gpt-4o-mini", openai_models)


def get_o1() -> str:
    """Get the latest o1 model (handles both preview and non-preview versions)."""
    from litellm import openai_models

    return _get_model_alias(r"^o1(?:-preview)?(?:-\d{4})?", openai_models)


def get_o1_mini() -> str:
    """Get the latest o1-mini model."""
    from litellm import openai_models

    return _get_model_alias(r"o1-mini", openai_models)


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
