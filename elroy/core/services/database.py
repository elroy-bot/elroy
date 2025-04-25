"""
Database service for ElroyContext.
"""

from functools import cached_property

from ...core.constants import allow_unused
from ...db.db_manager import DbManager, get_db_manager
from ...db.db_session import DbSession


class DatabaseService:
    """Provides database access with lazy initialization"""

    def __init__(self, config):
        self.config = config
        self._db = None

    @cached_property
    def db_manager(self) -> DbManager:
        assert self.config.database_url, "Database URL not set"
        return get_db_manager(self.config.database_url)

    @property
    def db(self) -> DbSession:
        if not self._db:
            raise ValueError("No db session open")
        return self._db

    def set_db_session(self, db: DbSession):
        self._db = db

    def unset_db_session(self):
        self._db = None

    @allow_unused
    def is_db_connected(self) -> bool:
        return bool(self._db)
