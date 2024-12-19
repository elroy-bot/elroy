import os
from pathlib import Path
from typing import Optional

SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3", ".db3"}


def path_to_sqlite_url(path_str: str) -> Optional[str]:
    """
    Check if a string represents a valid file path with a SQLite extension
    and convert it to a SQLite URL if it is.

    Valid inputs:
    - /absolute/path/to/database.db
    - relative/path/to/database.sqlite
    - C:\\path\\to\\database.db3
    - :memory:

    Args:
        path_str: A string that might represent a file path

    Returns:
        Optional[str]: SQLite URL if path is valid with correct extension, None otherwise
    """
    # Handle memory database special case
    if path_str == ":memory:":
        return "sqlite:///:memory:"

    try:
        # Convert to Path object to validate and normalize
        path = Path(path_str)

        # Check file extension
        if path.suffix.lower() not in SQLITE_EXTENSIONS:
            return None

        # Check if parent directory exists for absolute paths
        if path.is_absolute() and not path.parent.exists():
            return None

        # Convert to forward slashes and ensure proper formatting
        normalized_path = str(path).replace(os.sep, "/")

        # Ensure path starts with / for absolute paths
        if not normalized_path.startswith("/"):
            normalized_path = "/" + normalized_path

        return f"sqlite:///{normalized_path}"

    except (ValueError, RuntimeError):
        return None
