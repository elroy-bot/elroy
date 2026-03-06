import logging
from collections.abc import Generator
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from typing import Any

import chromadb
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, text
from sqlmodel import Session

from .. import PACKAGE_ROOT
from ..core.logging import get_logger
from .db_session import DbSession

logger = get_logger(__name__)


class DbManager:
    def __init__(self, url: str, chroma_path: Path | str | None = None):
        self.url = url
        if chroma_path:
            self.chroma_path = Path(chroma_path).expanduser()
        else:
            self.chroma_path = Path.home() / ".elroy" / "chroma"

    @cached_property
    def chroma_client(self) -> chromadb.ClientAPI:
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initializing ChromaDB at {self.chroma_path}")
        return chromadb.PersistentClient(path=str(self.chroma_path))

    @cached_property
    def engine(self) -> Engine:
        import sqlite3

        if not self.url.startswith("sqlite:///"):
            raise ValueError(f"Unsupported database URL: {self.url}. Must be a sqlite:/// URL")

        def _sqlite_connect(url):
            db_path = url.replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            logger.debug(f"SQLite version: {sqlite3.sqlite_version}")
            return conn

        return create_engine(self.url, creator=lambda: _sqlite_connect(self.url))

    @cached_property
    def alembic_config(self) -> Config:
        config = Config(Path(str(PACKAGE_ROOT / "db" / "sqlite" / "alembic" / "alembic.ini")))
        config.set_main_option("sqlalchemy.url", self.engine.url.render_as_string(hide_password=False))
        return config

    @property
    def alembic_script(self) -> ScriptDirectory:
        return ScriptDirectory.from_config(self.alembic_config)

    @contextmanager
    def open_session(self) -> Generator[DbSession, Any, None]:
        session = Session(self.engine)
        try:
            yield DbSession(self.url, session, self.chroma_client)
            if session.is_active:
                session.commit()
        except Exception:
            if session.is_active:
                session.rollback()
            raise
        finally:
            if session.is_active:
                session.close()

    def check_connection(self):
        try:
            with Session(self.engine) as session:
                session.exec(text("SELECT 1")).first()  # type: ignore
        except Exception as e:
            raise Exception(f"Could not connect to database {self.engine.url.render_as_string(hide_password=True)}: {e}") from e

        try:
            self.chroma_client.heartbeat()
        except Exception as e:
            raise Exception(f"Could not connect to ChromaDB at {self.chroma_path}: {e}") from e

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
        logging.getLogger("alembic").setLevel(logging.INFO)
        command.upgrade(self.alembic_config, "head")
