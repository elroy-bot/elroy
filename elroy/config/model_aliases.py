from typing import List

from toolz import last, pipe
from toolz.curried import filter


def get_sonnet() -> str:

    from litellm import anthropic_models

    return _get_model_alias("sonnet", anthropic_models)


def get_opus() -> str:

    from litellm import anthropic_models

    return _get_model_alias("opus", anthropic_models)


def _get_model_alias(match_str: str, models: List[str]) -> str:
    return pipe(
        models,
        filter(lambda x: match_str in x),
        sorted,
        last,
    )  # type: ignore
