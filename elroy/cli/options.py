import logging
import os
from functools import lru_cache
from multiprocessing import get_logger
from pathlib import Path
from typing import Any

import yaml
from toolz import assoc, merge, pipe
from toolz.curried import map, valfilter

from ..config.llm import DEFAULTS_CONFIG
from ..config.paths import get_default_sqlite_url
from ..core.constants import CLAUDE_3_5_SONNET

logger = get_logger()

DEPRECATED_KEYS = {
    "initial_context_refresh_wait_seconds",
    "context_refresh_target_tokens",
    "context_refresh_trigger_tokens",
}

MODEL_ALIASES = ["sonnet", "opus", "gpt4o", "gpt4o_mini", "o1", "o1_mini"]
CLI_ONLY_PARAMS = {"enable_assistant_greeting", "show_memory_panel"}


def resolve_model_alias(alias: str) -> str | None:
    return {
        "sonnet": CLAUDE_3_5_SONNET,
        "claude-3.5": CLAUDE_3_5_SONNET,
        "opus": "claude-opus-4-5-20251101",  # Updated to Claude 4.5 Opus
        "haiku": "claude-3-5-haiku-20241022",
        "o1": "openai/o1",
        "o1_mini": "openai/o1-mini",
        "gpt-5": "openai/gpt-5",
        "gpt5-mini": "openai/gpt-5-mini",
        "gpt5-nano": "openai/gpt-5-nano",
    }.get(alias)


def load_config_file_params(config_path: str | None = None) -> dict:
    # Looks for user specified config path, then merges with default values packaged with the lib

    user_config_path = config_path or os.environ.get(get_env_var_name("config_path"))

    if not user_config_path:
        return {}
    if user_config_path and not Path(user_config_path).is_absolute():
        logger.info("Resolving relative user config path")
        # convert to absolute path if not already, relative to working dir
        user_config_path = Path(user_config_path).resolve()
    return load_config_if_exists(user_config_path)


def get_env_var_name(parameter_name: str):
    return {
        "openai_api_key": "OPENAI_API_KEY",
        "openai_api_base": "OPENAI_API_BASE",
    }.get(parameter_name, f"ELROY_{parameter_name.upper()}")


def get_resolved_params(**kwargs) -> dict[str, Any]:
    """Get resolved parameter values from environment and config."""
    # n.b merge priority is lib default < user config file < env var < explicit CLI arg

    def convert_comma_separated_to_list(d: dict[str, Any]) -> dict[str, Any]:
        """Convert comma-separated string for background_ingest_paths to list if needed."""
        if "background_ingest_paths" in d and isinstance(d["background_ingest_paths"], str):
            paths = [p.strip() for p in d["background_ingest_paths"].split(",") if p.strip()]
            return assoc(d, "background_ingest_paths", paths)
        return d

    return pipe(
        [
            DEFAULTS_CONFIG,  # package defaults
            load_config_file_params(kwargs.get("config_path")),  # user specified config file
            {k: os.environ.get(get_env_var_name(k)) for k in DEFAULTS_CONFIG},  # env vars
            kwargs,  # explicit params
        ],
        map(valfilter(lambda x: x is not None and x != ())),
        merge,
        lambda d: assoc(d, "database_url", get_default_sqlite_url()) if not d.get("database_url") else d,
        convert_comma_separated_to_list,
    )


@lru_cache
def load_config_if_exists(user_config_path: str | None) -> dict:
    """
    Load configuration values in order of precedence:
    1. defaults.yml (base defaults)
    2. User config file (if provided)
    """

    if not user_config_path:
        return {}

    if not Path(user_config_path).exists():
        logger.info(f"User config file {user_config_path} not found")
        return {}
    if not Path(user_config_path).is_file():
        logging.error(f"User config path {user_config_path} is not a file")
        return {}
    try:
        with Path(user_config_path).open() as user_config_file:
            return yaml.safe_load(user_config_file)
    except Exception:
        logging.exception(f"Failed to load user config file {user_config_path}")
        return {}
