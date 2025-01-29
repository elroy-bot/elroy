import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import yaml
from toolz import assoc, dissoc, merge, pipe
from toolz.curried import map, valfilter
from typer import Option

from ..config.ctx import ElroyContext
from ..config.llm import DEFAULTS_CONFIG
from ..config.models_aliases import resolve_anthropic
from ..config.paths import get_default_sqlite_url

DEPRECATED_KEYS = {"initial_context_refresh_wait_seconds"}


def resolve_model_alias(alias: str) -> Optional[str]:
    if alias in ["sonnet", "opus", "haiku"]:
        return resolve_anthropic(alias)
    else:
        return {
            "gpt4o": "gpt-4o",
            "gpt4o_mini": "gpt-4o-mini",
            "o1": "o1",
            "o1_mini": "o1-mini",
        }.get(alias)


@lru_cache
def load_config_file_params(config_path: Optional[str] = None) -> Dict:
    # Looks for user specified config path, then merges with default values packaged with the lib

    user_config_path = config_path or os.environ.get(get_env_var_name("config_path"))

    if not user_config_path:
        return {}
    else:

        if user_config_path and not Path(user_config_path).is_absolute():
            logging.info("Resolving relative user config path")
            # convert to absolute path if not already, relative to working dir
            user_config_path = Path(user_config_path).resolve()
        return load_config_if_exists(user_config_path)


def ElroyOption(key: str, rich_help_panel: str, help: str, default_factory: Optional[Callable] = None, *args):
    """
    Typer options that have values in the user config file

    Creates a typer Option with value priority:
    1. CLI provided value (handled by typer)
    2. User config file value (if provided)
    3. defaults.yml value
    """

    return Option(
        *args,
        default_factory=default_factory if default_factory else lambda: load_config_file_params().get(key),
        envvar=get_env_var_name(key),
        rich_help_panel=rich_help_panel,
        help=help,
        show_default=str(DEFAULTS_CONFIG.get(key)),
        hidden=key in DEPRECATED_KEYS,
    )


def get_env_var_name(parameter_name: str):
    return {
        "openai_api_key": "OPENAI_API_KEY",
        "openai_api_base": "OPENAI_API_BASE",
        "openai_embedding_api_base": "OPENAI_API_BASE",
        "openai_organization": "OPENAI_ORGANIZATION",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
    }.get(parameter_name, "ELROY_" + parameter_name.upper())


def get_resolved_params(**kwargs) -> Dict[str, Any]:
    """Get resolved parameter values from environment and config."""
    # n.b merge priority is lib default < user config file < env var < explicit CLI arg

    params = pipe(
        [
            DEFAULTS_CONFIG,  # package defaults
            load_config_file_params(kwargs.get("config_path")),  # user specified config file
            {k: os.environ.get(get_env_var_name(k)) for k in DEFAULTS_CONFIG.keys()},  # env vars
            kwargs,  # explicit params
        ],
        map(valfilter(lambda x: x is not None)),
        merge,
        lambda d: assoc(d, "database_url", get_default_sqlite_url()) if not d.get("database_url") else d,
    )  # type: ignore

    assert isinstance(params, dict)

    invalid_params = set(params.keys()) - set(ElroyContext.__init__.__annotations__.keys())

    for k in invalid_params:
        if k in DEPRECATED_KEYS:
            logging.warning(f"Ignoring deprecated config (will be removed in future releases): '{k}'")
        else:
            logging.warning("Ignoring invalid parameter: {k}")

    params = dissoc(params, *invalid_params)
    return params


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
