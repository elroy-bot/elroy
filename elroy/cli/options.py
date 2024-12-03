import re
from typing import Any, Callable, Optional

import typer
from click import get_current_context
from toolz import pipe
from toolz.curried import filter
from typer import Option

from ..config.config import DEFAULT_CONFIG, load_defaults
from ..config.constants import MODEL_SELECTION_CONFIG_PANEL


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


def model_alias_typer_option(model_alias: str, description: str, resolver: Callable[[], str]):
    def set_chat_model(ctx: typer.Context, value: bool):
        if not value:
            return
        if not ctx.obj:
            ctx.obj = {}

        ctx.obj["chat_model"] = resolver()

    return typer.Option(
        False,
        f"--{model_alias}",
        help=f"Use {description}",
        rich_help_panel=MODEL_SELECTION_CONFIG_PANEL,
        callback=set_chat_model,
        is_eager=True,
    )


def resolve_anthropic(pattern: str) -> str:
    from litellm import anthropic_models

    return pipe(
        anthropic_models,
        filter(lambda x: re.search(pattern, x, re.IGNORECASE)),
        lambda x: max(x, key=claude_model_sort_key),  # type: ignore
    )


def claude_model_sort_key(model_name: str):
    # good lord claude names their models annoyingly
    version_match = re.search(r"claude-(\d+)(?:-(\d+))?", model_name)
    if version_match:
        major = int(version_match.group(1))
        minor = int(version_match.group(2)) if version_match.group(2) else 0
        version = float(f"{major}.{minor}")
    else:
        version = 0.0

    date_match = re.search(r"(\d{8})", model_name)
    date = int(date_match.group(1)) if date_match else 0

    return (version, date)
