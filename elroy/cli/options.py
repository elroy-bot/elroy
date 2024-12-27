import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Optional

import typer
import yaml
from click import get_current_context
from typer import Option

from ..config.config import DEFAULTS_CONFIG
from ..config.constants import CONFIG_FILE_KEY, MODEL_SELECTION_CONFIG_PANEL


def CliOption(yaml_key: str, envvar: Optional[str] = None, *args: Any, **kwargs: Any):
    """
    Creates a typer Option with value priority:
    1. CLI provided value (handled by typer)
    2. User config file value (if provided)
    3. defaults.yml value
    """

    def get_default():
        ctx = get_current_context()
        config_file = ctx.params.get(CONFIG_FILE_KEY)
        config_values = load_config_if_exists(config_file)
        return config_values.get(yaml_key) or DEFAULTS_CONFIG.get(yaml_key)

    if not envvar:
        envvar = f"ELROY_{yaml_key.upper()}"

    return Option(
        *args,
        default_factory=get_default,
        envvar=envvar,
        show_default=str(DEFAULTS_CONFIG.get(yaml_key)),
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


@lru_cache
def load_config_if_exists(user_config_path: str) -> dict:
    """
    Load configuration values in order of precedence:
    1. defaults.yml (base defaults)
    2. User config file (if provided)
    """

    if not Path(user_config_path).exists():
        logging.info(f"User config file {user_config_path} not found")
        return {}
    elif not Path(user_config_path).is_file():
        logging.error(f"User config path {user_config_path} is not a file")
        return {}
    else:
        try:
            with open(user_config_path, "r") as user_config_file:
                return yaml.safe_load(user_config_file)
        except Exception as e:
            logging.error(f"Failed to load user config file {user_config_path}: {e}")
            return {}
