import re
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from click import get_current_context
from toolz import last, pipe
from toolz.curried import filter
from typer import Option

from ..config.config import DEFAULT_CONFIG, load_defaults


def CliOption(yaml_key: str, envvar: Optional[str] = None, *args: Any, **kwargs: Any):
    """
    Creates a typer Option with value priority:
    1. CLI provided value (handled by typer)
    2. User config file value (if provided)
    3. defaults.yml value
    """

    def get_default():
        ctx = get_current_context()
        config_file = ctx.params.get("config_file")
        defaults = load_defaults(config_file)
        return defaults.get(yaml_key)

    if not envvar:
        envvar = f"ELROY_{yaml_key.upper()}"

    return Option(
        *args,
        default_factory=get_default,
        envvar=envvar,
        show_default=str(DEFAULT_CONFIG.get(yaml_key)),
        **kwargs,
    )


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


def get_cli_option(option_name: str):
    return CliOption(
        option_name,
        help=f"Use {CHAT_MODEL_ALIASES[option_name].description}",
        is_flag=True,
        default=False,
        rich_help_panel="Model Selection",
    )


def generate_model_options():
    """Generate Typer CLI options for each model alias"""
    options = {}
    for alias_key, alias in CHAT_MODEL_ALIASES.items():
        option_name = f"{alias_key.replace('-', '_')}"  # Convert hyphens to underscores for valid Python names
        options[option_name] = CliOption(
            option_name, help=f"Use {alias.description}", is_flag=True, default=False, rich_help_panel="Model Selection"
        )
    return options


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
