import re
from functools import cached_property
from pathlib import Path

from sqlalchemy import Engine, NullPool, create_engine
from sqlmodel import Session, text

from ... import PACKAGE_ROOT
from ..db_manager import DbManager
from .postgres_session import PostgresSession


class PostgresManager(DbManager[PostgresSession]):
    def __init__(self, url):
        self.session_class = PostgresSession
        super().__init__(url)

    @classmethod
    def is_url_valid(cls, url: str) -> bool:
        pattern = r"^postgresql(?:ql)?:\/\/"  # Protocol
        pattern += r"(?:(?:[^:@\/]+)(?::([^@\/]+))?@)?"  # User and password
        pattern += r"[^:@\/]+(?::\d+)?"  # Host and port
        pattern += r"\/[^?\/]+"  # Database name
        pattern += r"(?:\?[^#\/]+)?$"  # Query parameters (optional)

        return bool(re.match(pattern, url))

    @cached_property
    def engine(self) -> Engine:
        if not self.is_url_valid(self.url):
            raise ValueError(f"Invalid database URL: {self.url}")

        return create_engine(self.url, poolclass=NullPool)

    def _get_config_path(self):
        return Path(str(PACKAGE_ROOT / "db" / "postgres" / "alembic" / "alembic.ini"))

    def check_connection(self):
        try:
            with Session(self.engine) as session:
                session.exec(text("SELECT 1")).first()  # type: ignore
        except Exception as e:
            raise Exception(f"Could not connect to database {self.engine.url.render_as_string(hide_password=True)}: {e}") from e

    def migrate(self):
        with Session(self.engine) as session:
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector;"))  # type: ignore

        return super().migrate()
