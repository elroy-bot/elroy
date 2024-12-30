import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from click import get_current_context
from toolz import merge
from typer import Option

from ..config.config import DEFAULTS_CONFIG
from ..config.constants import CONFIG_FILE_KEY
from ..config.models import resolve_anthropic
from ..config.paths import get_default_config_path


def resolve_model_alias(alias: str) -> Optional[str]:
    if alias in ["sonnet", "opus", "haiku"]:
        return resolve_anthropic(alias)
    else:
        return {
            "4o": "gpt-4o",
            "4o-mini": "gpt-4o-mini",
            "o1": "o1",
            "o1-mini": "o1-mini",
        }.get(alias)


@lru_cache
def get_config_params(config_path: Optional[str] = None) -> Dict:
    ctx = get_current_context(True)
    ctx_path = ctx.params.get(CONFIG_FILE_KEY) if ctx else None

    user_config_path = config_path or ctx_path or get_default_config_path()

    return merge(DEFAULTS_CONFIG, load_config_if_exists(user_config_path))


def CliOption(yaml_key: str, envvar: Optional[str] = None, *args: Any, **kwargs: Any):
    """
    Creates a typer Option with value priority:
    1. CLI provided value (handled by typer)
    2. User config file value (if provided)
    3. defaults.yml value
    """

    return Option(
        *args,
        default_factory=lambda: get_config_params().get(yaml_key),
        envvar=envvar or f"ELROY_{yaml_key.upper()}",
        show_default=str(DEFAULTS_CONFIG.get(yaml_key)),
        **kwargs,
    )


@lru_cache
def load_config_if_exists(user_config_path: Optional[str]) -> dict:
    """
    Load configuration values in order of precedence:
    1. defaults.yml (base defaults)
    2. User config file (if provided)
    """

    if not user_config_path:
        return {}

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
