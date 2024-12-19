import logging
import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Type

from sqlalchemy import Engine, NullPool, create_engine, select
from sqlalchemy.orm import aliased
from sqlmodel import Session, and_, func, select, text
from toolz import pipe
from toolz.curried import do, map

from ... import PACKAGE_ROOT
from ...config.constants import RESULT_SET_LIMIT_COUNT
from ..db_manager import DbManager
from ..db_models import EmbeddableSqlModel, EmbeddableType, VectorStorage


class PostgresManager(DbManager):

    @classmethod
    def is_valid_url(cls, url):
        pattern = r"^postgresql(?:ql)?:\/\/"  # Protocol
        pattern += r"(?:(?:[^:@\/]+)(?::([^@\/]+))?@)?"  # User and password
        pattern += r"[^:@\/]+(?::\d+)?"  # Host and port
        pattern += r"\/[^?\/]+"  # Database name
        pattern += r"(?:\?[^#\/]+)?$"  # Query parameters (optional)

        return bool(re.match(pattern, url))

    @classmethod
    def get_engine(cls, url: str) -> Engine:
        if not cls.is_valid_url(url):
            raise ValueError(f"Invalid database URL: {url}")

        return create_engine(url, poolclass=NullPool)

    def get_embedding(self, row: EmbeddableSqlModel) -> Optional[List[float]]:
        return self.exec(
            select(VectorStorage.embedding_data).where(
                VectorStorage.source_id == row.id, VectorStorage.source_type == row.__class__.__name__
            )  # type: ignore
        ).first()  # type: ignore

    def get_vector_storage_row(self, row: EmbeddableSqlModel) -> Optional[VectorStorage]:
        return self.session.exec(
            select(VectorStorage).where(VectorStorage.source_type == row.__class__.__name__, VectorStorage.source_id == row.id)
        ).first()

    def find_redundant_pairs(
        self,
        table: Type[EmbeddableType],
        l2_distance_threshold: float,
        user_id: int,
        limit: int = 1,
    ) -> Iterable[Tuple[EmbeddableType, EmbeddableType]]:
        """
        Query an EmbeddableSqlModel using a self-join and return the closest pair of rows in similarity
        over the L2_PERCENT_CLOSER_THAN_RANDOM_THRESHOLD.

        Args:
            context (ElroyContext): The Elroy context.
            table (Type[EmbeddableSqlModel]): The table to query.
            filter_clause (Any, optional): Additional filter clause. Defaults to lambda: True.

        Returns:
            Optional[Tuple[EmbeddableSqlModel, EmbeddableSqlModel, float]]:
            A tuple containing the two closest rows and their similarity score,
            or None if no pair is found above the threshold.
        """
        t1 = aliased(table, name="t1")
        t2 = aliased(table, name="t2")

        v1 = aliased(VectorStorage, name="v1")
        v2 = aliased(VectorStorage, name="v2")

        distance_exp = v1.embedding_data.l2_distance(v2.embedding_data).label("distance")  # type: ignore

        yield from pipe(
            self.exec(
                select(t1, t2, distance_exp)
                .join(t2, t1.id < t2.id)  # type: ignore Ensure we don't compare a row with itself
                .join(v1, (v1.source_type == table.__name__) & (v1.source_id == t1.id))  # type: ignore
                .join(v2, (v2.source_type == table.__name__) & (v2.source_id == t2.id))  # type: ignore
                .where(
                    t1.user_id == user_id,
                    t2.user_id == user_id,
                    t1.is_active == True,
                    t2.is_active == True,
                    distance_exp < l2_distance_threshold,
                )
                .order_by(func.random())  # order by random to lessen chance of infinite loops
                .limit(limit)
            ),
            map(do(lambda row: logging.info(f"Found redundant pair: {row[0].id} and {row[1].id}. Distance = {row[2]}"))),
            map(lambda row: (row[0], row[1])),
        )  # type: ignore

    def update_embedding(self, vector_storage: VectorStorage, embedding: List[float], embedding_text_md5: str):
        vector_storage.embedding_data = embedding
        vector_storage.embedding_text_md5 = embedding_text_md5
        self.session.add(vector_storage)
        self.session.commit()

    def insert_embedding(self, row: EmbeddableSqlModel, embedding_data, embedding_text_md5):
        row_id = row.id
        assert row_id
        self.session.add(
            VectorStorage(
                source_type=row.__class__.__name__, source_id=row_id, embedding_data=embedding_data, embedding_text_md5=embedding_text_md5
            )
        )
        self.session.commit()

    def query_vector(
        self, l2_distance_threshold: float, table: Type[EmbeddableSqlModel], user_id: int, query: List[float]
    ) -> Iterable[EmbeddableSqlModel]:
        """
        Perform a vector search on the specified table using the given query.

        Args:
            query (str): The search query.
            table (EmbeddableSqlModel): The SQLModel table to search.

        Returns:
            List[Tuple[Fact, float]]: A list of tuples containing the matching Fact and its similarity score.
        """

        # Use pgvector's <-> operator for L2 distance
        distance_exp = VectorStorage.embedding_data.l2_distance(query).label("distance")  # type: ignore

        return pipe(
            self.exec(
                select(table, distance_exp)
                .join(
                    VectorStorage,
                    and_(
                        VectorStorage.source_type == table.__name__,
                        VectorStorage.source_id == table.id,
                    ),
                )
                .where(
                    and_(
                        table.user_id == user_id,
                        table.is_active == True,
                        distance_exp < l2_distance_threshold,
                    )
                )
                .order_by(distance_exp)
                .limit(RESULT_SET_LIMIT_COUNT)  # type: ignore
            ),
            map(lambda row: row[0]),
        )

    @classmethod
    def _get_config_path(cls):
        return Path(str(PACKAGE_ROOT / "db" / "postgres" / "alembic" / "alembic.ini"))

    @classmethod
    def _migrate_if_needed(cls, engine: Engine):
        with Session(engine) as session:
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector;"))  # type: ignore

        return super()._migrate_if_needed(engine)
