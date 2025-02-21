import logging
from abc import ABC
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from typing import Any, Generator, Generic, Type, TypeVar

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine
from sqlmodel import Session

from .db_session import DbSession

TSession = TypeVar("TSession", bound=DbSession)


class DbManager(ABC, Generic[TSession]):
    def __init__(self, url: str):
        self.url = url
        self.session_class: Type[TSession]

    @cached_property
    def engine(self) -> Engine:
        raise NotImplementedError

    @cached_property
    def alembic_config(self):
        config = Config(self._get_config_path())
        config.set_main_option("sqlalchemy.url", self.engine.url.render_as_string(hide_password=False))
        return config

    @property
    def alembic_script(self) -> ScriptDirectory:
        return ScriptDirectory.from_config(self.alembic_config)

    @classmethod
    def is_url_valid(cls, url: str) -> bool:
        raise NotImplementedError

    @contextmanager
    def open_session(self) -> Generator[TSession, Any, None]:
        session = Session(self.engine)
        try:
            yield self.session_class(self.url, session)
            if session.is_active:  # Only commit if the session is still active
                session.commit()
        except Exception:
            if session.is_active:  # Only rollback if the session is still active
                session.rollback()
            raise
        finally:
            if session.is_active:  # Only close if not already closed
                session.close()
                session = None

    def _get_config_path(self) -> Path:
        raise NotImplementedError

    def check_connection(self):
        raise NotImplementedError

    def migrate_if_needed(self):
        if self.is_migration_needed():
            self.migrate()

    def is_migration_needed(self) -> bool:
        self.check_connection()
        with self.engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            head_rev = self.alembic_script.get_current_head()
            return current_rev != head_rev

    def migrate(self):
        """Check if all migrations have been run.
        Returns True if migrations are up to date, False otherwise."""
        logging.getLogger("alembic").setLevel(logging.INFO)

        command.upgrade(self.alembic_config, "head")


def get_db_manager(url: str) -> DbManager:

    from ..db.postgres.postgres_manager import PostgresManager
    from ..db.sqlite.sqlite_manager import SqliteManager

    if url.startswith("postgresql://"):
        return PostgresManager(url)
    elif url.startswith("sqlite:///"):
        return SqliteManager(url)
    else:
        raise ValueError(f"Unsupported database URL: {url}. Must be either a postgresql:// or sqlite:/// URL")
