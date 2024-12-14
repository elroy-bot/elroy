import re
from functools import partial
from typing import List, Optional, Tuple

from toolz import assoc, first, pipe
from toolz.curried import filter

from .config import ChatModel


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
