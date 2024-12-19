from pathlib import Path
from platformdirs import user_data_dir

APP_NAME = "elroy"
APP_AUTHOR = "elroy-bot"

def get_elroy_home() -> Path:
    """Get the Elroy home directory, creating it if it doesn't exist.
    
    Returns platform-appropriate path:
    - Windows: C:\\Users\\<username>\\AppData\\Local\\elroy-bot\\elroy
    - macOS: ~/Library/Application Support/elroy
    - Linux: ~/.local/share/elroy
    """
    data_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
