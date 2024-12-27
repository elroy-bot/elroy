from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir

APP_NAME = "elroy"
APP_AUTHOR = "elroy-bot"


def get_elroy_home() -> Path:
    """Get the Elroy home directory, creating it if it doesn't exist.

    Returns platform-appropriate path:
    - Windows: C:\\Users\\<username>\\AppData\\Local\\elroy-bot\\elroy
    - macOS: ~/Library/Application Support/elroy
    - Linux: ~/.local/share/elroy
    """
    data_dir = Path(user_data_dir(APP_NAME))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_default_config_path() -> Path:
    return get_elroy_home() / "elroy.conf.yaml"


def get_elroy_cache() -> Path:
    """Get the Elroy cache directory, creating it if it doesn't exist.

    Returns platform-appropriate path:
    - Windows: C:\\Users\\<username>\\AppData\\Local\\elroy-bot\\elroy\\Cache
    - macOS: ~/Library/Caches/elroy
    - Linux: ~/.cache/elroy
    """
    cache_dir = Path(user_cache_dir(APP_NAME))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_prompt_history_path():
    return get_elroy_cache() / ".history"


def get_default_sqlite_url():
    return f"sqlite:///{get_elroy_cache() / 'elroy.db'}"
