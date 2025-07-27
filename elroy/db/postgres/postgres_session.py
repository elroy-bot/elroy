from typing import Iterable, List, Optional, Type, Union

from sqlalchemy import select
from sqlmodel import and_, select
from toolz import pipe
from toolz.curried import map

from ..db_models import EmbeddableSqlModel, VectorStorage
from ..db_session import DbSession


class PostgresSession(DbSession):

    def get_embedding(self, row: EmbeddableSqlModel) -> Optional[List[float]]:
        return self.session.exec(
            select(VectorStorage.embedding_data).where(
                VectorStorage.source_id == row.id, VectorStorage.source_type == row.__class__.__name__
            )  # type: ignore
        ).first()  # type: ignore

    def get_vector_storage_row(self, row: EmbeddableSqlModel) -> Optional[VectorStorage]:
        return self.session.exec(
            select(VectorStorage).where(VectorStorage.source_type == row.__class__.__name__, VectorStorage.source_id == row.id)
        ).first()

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
        self,
        l2_distance_threshold: float,
        tables: Union[Type[EmbeddableSqlModel], List[Type[EmbeddableSqlModel]]],
        user_id: int,
        query: List[float],
        limit_per_table: int = 10,
    ) -> Iterable[EmbeddableSqlModel]:
        """
        Perform a vector search on the specified table(s) using the given query.

        Args:
            l2_distance_threshold: Maximum L2 distance for results
            tables: Single table or list of tables to search
            user_id: User ID to filter by
            query: The embedding vector to search with
            limit_per_table: Maximum results per table

        Returns:
            Iterable of EmbeddableSqlModel results from all tables
        """
        # Normalize to list
        if not isinstance(tables, list):
            tables = [tables]

        all_results = []

        for table in tables:
            # Use pgvector's <-> operator for L2 distance
            distance_exp = VectorStorage.embedding_data.l2_distance(query).label("distance")  # type: ignore

            results = pipe(
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
                    .limit(limit_per_table)  # type: ignore
                ),
                map(lambda row: row[0]),
                list,
            )
            all_results.extend(results)

        return iter(all_results)
