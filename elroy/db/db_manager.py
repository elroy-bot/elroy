import contextlib
import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from typing import Any, Generator, Iterable, List, Optional, Tuple, Type

import typer
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine
from sqlmodel import Session, select, text

from .db_models import EmbeddableSqlModel, EmbeddableType, VectorStorage


class DbManager(ABC):
    def __init__(self, url: str, session: Session):
        self.url = url
        self.session = session

    @classmethod
    def get_engine(cls, url: str) -> Engine:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def is_valid_url(cls, url: str) -> bool:
        raise NotImplementedError

    @property
    def vector_distance_operator(self) -> str:
        """Returns the SQL operator for vector distance calculations"""
        raise NotImplementedError

    @abstractmethod
    def get_vector_storage_row(self, row: EmbeddableSqlModel) -> Optional[VectorStorage]:
        raise NotImplementedError

    @abstractmethod
    def insert_embedding(self, row: EmbeddableSqlModel, embedding_data: List[float], embedding_text_md5: str):
        raise NotImplementedError

    def update_embedding(self, vector_storage: VectorStorage, embedding: List[float], embedding_text_md5: str):
        raise NotImplementedError

    @abstractmethod
    def find_redundant_pairs(
        self,
        table: Type[EmbeddableType],
        l2_distance_threshold: float,
        user_id: int,
        limit: int = 1,
    ) -> Iterable[Tuple[EmbeddableType, EmbeddableType]]:
        raise NotImplementedError

    @abstractmethod
    def get_embedding(self, row: EmbeddableSqlModel) -> Optional[List[float]]:
        raise NotImplementedError

    def get_embedding_text_md5(self, row: EmbeddableSqlModel) -> Optional[str]:
        return self.session.exec(
            select(VectorStorage.embedding_text_md5).where(
                VectorStorage.source_id == row.id, VectorStorage.source_type == row.__class__.__name__
            )
        ).first()

    @abstractmethod
    def query_vector(
        self, l2_distance_threshold: float, table: Type[EmbeddableSqlModel], user_id: int, query: List[float]
    ) -> Iterable[EmbeddableSqlModel]:
        raise NotImplementedError

    @classmethod
    @contextmanager
    def open_session(cls, url: str, check_migrations: bool) -> Generator["DbManager", Any, None]:
        engine = cls.get_engine(url)
        if check_migrations:
            cls._migrate_if_needed(engine)

        session = Session(engine)
        try:
            yield cls(url, session)
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

    @contextmanager
    def get_new_session(self) -> Generator["DbManager", Any, None]:
        """
        Spawns a new DbManager with same params
        """

        with self.__class__.open_session(self.url, False) as db:
            yield db

    @property
    def exec(self):
        return self.session.exec

    @property
    def rollback(self):
        return self.session.rollback

    @property
    def add(self):
        return self.session.add

    @property
    def commit(self):
        return self.session.commit

    @property
    def refresh(self):
        return self.session.refresh

    @classmethod
    def _get_config_path(cls) -> Path:
        raise NotImplementedError

    @classmethod
    def _migrate_if_needed(cls, engine: Engine):
        """Check if all migrations have been run.
        Returns True if migrations are up to date, False otherwise."""
        try:
            with Session(engine) as session:
                session.exec(text("SELECT 1")).first()  # type: ignore
        except Exception as e:
            logging.error(f"Database connectivity check failed: {e}")
            raise typer.BadParameter(
                f"Could not connect to database at {engine.url.render_as_string(hide_password=True)}. Please check if database is running and connection URL is correct."
            )

        """Check if all migrations have been run.
        Returns True if migrations are up to date, False otherwise."""
        config = Config(cls._get_config_path())
        config.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))

        script = ScriptDirectory.from_config(config)

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            head_rev = script.get_current_head()

            if current_rev != head_rev:
                # Capture and redirect alembic output to logging

                with contextlib.redirect_stdout(StringIO()) as stdout:
                    command.upgrade(config, "head")
                    for line in stdout.getvalue().splitlines():
                        if line.strip():
                            logging.info(f"Alembic: {line.strip()}")
            else:
                logging.debug("Database is up to date.")
