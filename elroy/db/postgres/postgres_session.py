from collections.abc import Iterable
from typing import Any, cast

from sqlmodel import and_, select
from toolz import pipe
from toolz.curried import map

from ...core.constants import RESULT_SET_LIMIT_COUNT
from ..db_models import EmbeddableSqlModel, VectorStorage
from ..db_session import DbSession


class PostgresSession(DbSession):
    def get_embedding(self, row: EmbeddableSqlModel) -> list[float] | None:
        return self.session.exec(
            select(VectorStorage.embedding_data).where(
                VectorStorage.source_id == row.id, VectorStorage.source_type == row.__class__.__name__
            )
        ).first()  # type: ignore

    def get_vector_storage_row(self, row: EmbeddableSqlModel) -> VectorStorage | None:
        return self.session.exec(
            select(VectorStorage).where(VectorStorage.source_type == row.__class__.__name__, VectorStorage.source_id == row.id)
        ).first()

    def update_embedding(self, vector_storage: VectorStorage, embedding: list[float], embedding_text_md5: str):
        vector_storage.embedding_data = embedding
        vector_storage.embedding_text_md5 = embedding_text_md5
        self.session.add(vector_storage)
        self.session.commit()

    def insert_embedding(self, row: EmbeddableSqlModel, embedding_data, embedding_text_md5):
        row_id = row.id
        assert row_id
        self.session.add(
            VectorStorage(
                source_type=row.__class__.__name__,
                source_id=row_id,
                embedding_data=embedding_data,
                embedding_text_md5=embedding_text_md5,
                user_id=row.user_id,
            )
        )
        self.session.commit()

    def query_vector(
        self, l2_distance_threshold: float, table: type[EmbeddableSqlModel], user_id: int, query: list[float]
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
                        cast(Any, table.is_active).is_(True),
                        distance_exp < l2_distance_threshold,
                    )
                )
                .order_by(distance_exp)
                .limit(RESULT_SET_LIMIT_COUNT)
            ),
            map(lambda row: row[0]),
        )
