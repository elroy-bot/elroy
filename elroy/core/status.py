"""Thread-safe registry for background task status messages."""

import threading

_lock = threading.Lock()
_background_statuses: dict[str, str] = {}


def set_background_status(key: str, message: str) -> None:
    """Record that a background operation is running."""
    with _lock:
        _background_statuses[key] = message


def clear_background_status(key: str) -> None:
    """Clear a background operation status."""
    with _lock:
        _background_statuses.pop(key, None)


def get_background_status() -> str | None:
    """Return the first active background status message, or None."""
    with _lock:
        if _background_statuses:
            return next(iter(_background_statuses.values()))
        return None
