import os
from pathlib import Path

APP_NAME = "elroy"


def get_home_dir() -> Path:
    """Get the Elroy home directory (~/.elroy), creating it if it doesn't exist.

    Can be overridden with ELROY_HOME environment variable.
    """
    home_dir = Path(env_home) if (env_home := os.environ.get("ELROY_HOME")) else Path.home() / ".elroy"

    home_dir.mkdir(parents=True, exist_ok=True)
    return home_dir


def get_save_dir() -> Path:
    path = get_home_dir() / "saves"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_default_config_path() -> Path:
    return get_home_dir() / "elroy.conf.yaml"


def get_cache_dir() -> Path:
    cache_dir = get_home_dir() / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_prompt_history_path():
    return get_cache_dir() / "history"


def get_default_sqlite_url():
    return f"sqlite:///{get_home_dir() / 'elroy.db'}"


def get_log_file_path():
    logs_dir = get_home_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "elroy.log"
