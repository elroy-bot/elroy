import logging
import re
import sqlite3
from functools import cached_property
from pathlib import Path

import sqlite_vec
from sqlalchemy import Engine, create_engine, text
from sqlmodel import Session

from ... import PACKAGE_ROOT
from ..db_manager import DbManager
from .sqlite_session import SqliteSession


class SqliteManager(DbManager):
    def __init__(self, url):
        self.session_class = SqliteSession
        super().__init__(url)

    def _get_config_path(self):
        return Path(str(PACKAGE_ROOT / "db" / "sqlite" / "alembic" / "alembic.ini"))

    def check_connection(self):
        try:
            with Session(self.engine) as session:
                session.exec(text("SELECT 1")).first()  # type: ignore
        except Exception as e:
            if "ELFCLASS32" in str(e) and str(self.engine.url).startswith("sqlite"):
                raise Exception(
                    "Architecture mismatch between compiled SQLite extension and env os. If you are using docker, consider adding --platform linux/amd64 to your command, or provide a Postgres value for --database-url."
                )
            else:
                logging.error(f"Database connectivity check failed: {e}")
                raise Exception(f"Could not connect to database {self.engine.url.render_as_string(hide_password=True)}: {e}")

    @classmethod
    def is_url_valid(cls, url: str) -> bool:
        pattern = r"^sqlite:\/\/"  # Protocol
        pattern += r"(?:\/)?"  # Optional extra slash for Windows absolute paths
        pattern += r"(?:"  # Start of non-capturing group for alternatives
        pattern += r":memory:|"  # In-memory database option
        pattern += r"\/[^?]+"  # Path to database file
        pattern += r")"  # End of alternatives group
        pattern += r"(?:\?[^#]+)?$"  # Query parameters (optional)
        return bool(re.match(pattern, url))

    @cached_property
    def engine(self) -> Engine:
        def _sqlite_connect(url):
            # Strip sqlite:/// prefix if present
            db_path = url.replace("sqlite:///", "")
            conn = sqlite3.connect(db_path)
            logging.debug(f"SQLite version: {sqlite3.sqlite_version}")  # Shows SQLite version

            logging.debug("Loading vec extension")
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            logging.debug("Vec extension loaded, verifying hello world vector query")
            # Let's verify the function exists after loading
            try:
                conn.execute(
                    "SELECT vec_distance_L2(?, ?)",
                    (sqlite_vec.serialize_float32([0.0]), sqlite_vec.serialize_float32([0.0])),
                )
            except sqlite3.OperationalError as e:
                logging.debug(f"Failed to verify vec_distance_L2 function: {e}")
                raise
            logging.debug("Connection vec extension enabled and verified")
            return conn

        if not self.__class__.is_url_valid(self.url):
            raise ValueError(f"Invalid database URL: {self.url}")

        return create_engine(
            self.url,
            creator=lambda: _sqlite_connect(self.url),
        )
