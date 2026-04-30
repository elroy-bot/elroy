from pathlib import Path

from ..db.db_manager import DbManager
from .ctx import ElroyConfig


def get_db_manager(config: ElroyConfig) -> DbManager:
    assert config.database_url, "Database URL not set"
    chroma_path = Path(config.chroma_path) if config.chroma_path else None
    return DbManager(config.database_url, chroma_path=chroma_path)
