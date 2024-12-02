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
