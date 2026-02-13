"""ChromaDB manager for vector storage operations."""

import re
from collections.abc import Generator
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from typing import Any

import chromadb
from sqlalchemy import Engine, create_engine, text
from sqlmodel import Session

from ... import PACKAGE_ROOT
from ...core.logging import get_logger
from ..db_manager import DbManager
from .chroma_session import ChromaSession

logger = get_logger(__name__)


class ChromaManager(DbManager):
    """Database manager that uses ChromaDB for vector storage.

    Architecture:
    - Relational DB (SQLite/Postgres) for entity data - uses URL from config
    - ChromaDB for vector storage - persistent storage in ~/.elroy/chroma/
    - ChromaSession bridges both backends
    """

    def __init__(self, url: str, chroma_path: Path | str | None = None):
        self.session_class = ChromaSession
        if chroma_path:
            self.chroma_path = Path(chroma_path).expanduser()
        else:
            self.chroma_path = Path.home() / ".elroy" / "chroma"
        super().__init__(url)

    @cached_property
    def chroma_client(self) -> chromadb.ClientAPI:
        """Initialize persistent ChromaDB client."""
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initializing ChromaDB at {self.chroma_path}")
        return chromadb.PersistentClient(path=str(self.chroma_path))

    @cached_property
    def engine(self) -> Engine:
        """Create relational DB engine based on URL."""
        # Delegate to SQLite or Postgres engine creation
        if self.url.startswith("sqlite:///"):
            return self._create_sqlite_engine()
        elif self.url.startswith("postgresql://"):
            return self._create_postgres_engine()
        else:
            raise ValueError(f"Unsupported database URL for ChromaDB backend: {self.url}")

    def _create_sqlite_engine(self) -> Engine:
        """Create SQLite engine (vectors handled by ChromaDB, not sqlite-vec)."""
        import sqlite3

        def _sqlite_connect(url):
            db_path = url.replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            logger.debug(f"SQLite version: {sqlite3.sqlite_version}")
            # Note: No vec extension needed - vectors are in ChromaDB
            return conn

        return create_engine(self.url, creator=lambda: _sqlite_connect(self.url))

    def _create_postgres_engine(self) -> Engine:
        """Create PostgreSQL engine (vectors handled by ChromaDB, not pgvector)."""
        return create_engine(self.url)

    @contextmanager
    def open_session(self) -> Generator[ChromaSession, Any, None]:
        """Create a session that bridges both relational DB and ChromaDB."""
        session = Session(self.engine)
        try:
            yield ChromaSession(self.url, session, self.chroma_client)
            if session.is_active:
                session.commit()
        except Exception:
            if session.is_active:
                session.rollback()
            raise
        finally:
            if session.is_active:
                session.close()

    def _get_config_path(self) -> Path:
        """Get Alembic config path based on underlying DB type."""
        if self.url.startswith("sqlite:///"):
            return Path(str(PACKAGE_ROOT / "db" / "sqlite" / "alembic" / "alembic.ini"))
        elif self.url.startswith("postgresql://"):
            return Path(str(PACKAGE_ROOT / "db" / "postgres" / "alembic" / "alembic.ini"))
        else:
            raise ValueError(f"Unsupported database URL: {self.url}")

    def check_connection(self):
        """Verify both relational DB and ChromaDB are accessible."""
        # Check relational DB
        try:
            with Session(self.engine) as session:
                session.exec(text("SELECT 1")).first()  # type: ignore
        except Exception as e:
            logger.error(f"Relational database connectivity check failed: {e}")
            raise Exception(f"Could not connect to database {self.engine.url.render_as_string(hide_password=True)}: {e}") from e

        # Check ChromaDB
        try:
            self.chroma_client.heartbeat()
        except Exception as e:
            logger.error(f"ChromaDB connectivity check failed: {e}")
            raise Exception(f"Could not connect to ChromaDB at {self.chroma_path}: {e}") from e

    @classmethod
    def is_url_valid(cls, url: str) -> bool:
        """Validate database URL (supports both SQLite and Postgres)."""
        sqlite_pattern = r"^sqlite:\/\/(?:\/)?(?::memory:|\/[^?]+)(?:\?[^#]+)?$"
        postgres_pattern = r"^postgresql:\/\/.+"
        return bool(re.match(sqlite_pattern, url) or re.match(postgres_pattern, url))
