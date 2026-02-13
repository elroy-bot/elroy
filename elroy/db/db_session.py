from abc import ABC, abstractmethod
from collections.abc import Iterable

from sqlmodel import Session, select
from toolz import compose
from toolz.curried import do

from .db_models import EmbeddableSqlModel, VectorStorage


class DbSession(ABC):
    def __init__(self, url: str, session: Session):
        self.url = url
        self.session = session

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
    def persist(self):
        return compose(
            do(self.session.expunge),
            do(self.session.refresh),
            do(lambda x: self.session.commit()),
            do(self.session.add),
        )

    @property
    def refresh(self):
        return self.session.refresh

    @abstractmethod
    def get_vector_storage_row(self, row: EmbeddableSqlModel) -> VectorStorage | None:
        raise NotImplementedError

    @abstractmethod
    def insert_embedding(self, row: EmbeddableSqlModel, embedding_data: list[float], embedding_text_md5: str):
        raise NotImplementedError

    def update_embedding(self, vector_storage: VectorStorage, embedding: list[float], embedding_text_md5: str):
        raise NotImplementedError

    @abstractmethod
    def get_embedding(self, row: EmbeddableSqlModel) -> list[float] | None:
        raise NotImplementedError

    def get_embedding_text_md5(self, row: EmbeddableSqlModel) -> str | None:
        return self.session.exec(
            select(VectorStorage.embedding_text_md5).where(
                VectorStorage.source_id == row.id,
                VectorStorage.source_type == row.__class__.__name__,
            )
        ).first()

    @abstractmethod
    def query_vector(
        self, l2_distance_threshold: float, table: type[EmbeddableSqlModel], user_id: int, query: list[float]
    ) -> Iterable[EmbeddableSqlModel]:
        raise NotImplementedError
