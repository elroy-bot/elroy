import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable, List, Optional, Type

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine
from sqlmodel import Session, select

from .db_models import EmbeddableSqlModel, VectorStorage


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

    @abstractmethod
    def get_vector_storage_row(self, row: EmbeddableSqlModel) -> Optional[VectorStorage]:
        raise NotImplementedError

    @abstractmethod
    def insert_embedding(self, row: EmbeddableSqlModel, embedding_data: List[float], embedding_text_md5: str):
        raise NotImplementedError

    def update_embedding(self, vector_storage: VectorStorage, embedding: List[float], embedding_text_md5: str):
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
    def open_session(cls, url: str) -> Generator["DbManager", Any, None]:
        engine = cls.get_engine(url)
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

        with self.__class__.open_session(self.url) as db:
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
    def check_connection(cls, engine: Engine):
        raise NotImplementedError

    @classmethod
    def get_config(cls, engine: Engine):
        config = Config(cls._get_config_path())
        config.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
        return config

    @classmethod
    def is_migration_needed(cls, engine: Engine) -> bool:
        cls.check_connection(engine)
        script = ScriptDirectory.from_config(cls.get_config(engine))
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            head_rev = script.get_current_head()
            return current_rev != head_rev

    @classmethod
    def migrate(cls, engine: Engine):
        """Check if all migrations have been run.
        Returns True if migrations are up to date, False otherwise."""
        config = cls.get_config(engine)
        logging.getLogger("alembic").setLevel(logging.INFO)

        command.upgrade(config, "head")
