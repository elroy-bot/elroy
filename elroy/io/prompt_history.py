"""Persistence helpers for the Textual prompt history."""

from pathlib import Path

from ..config.paths import get_prompt_history_path
from ..core.logging import get_logger

logger = get_logger()


class PromptHistoryStore:
    """Load and append prompt history without exposing file I/O to the app."""

    def __init__(self, path: Path | None = None):
        self.path = path or Path(get_prompt_history_path())

    def load(self) -> list[str]:
        try:
            if self.path.exists():
                lines = self.path.read_text().splitlines()
                return [text for line in reversed(lines) if line.startswith("+") and self._is_recallable(text := line[1:])]
        except Exception:
            logger.warning("Failed to load prompt history from %s", self.path, exc_info=True)
        return []

    def append(self, text: str) -> None:
        if not self._is_recallable(text):
            return
        try:
            with self.path.open("a") as file_obj:
                file_obj.write(f"+{text}\n")
        except Exception:
            logger.warning("Failed to append prompt history to %s", self.path, exc_info=True)

    @staticmethod
    def _is_recallable(text: str) -> bool:
        stripped = text.strip()
        return bool(stripped) and not stripped.startswith("/")
