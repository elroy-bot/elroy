from typing import Iterable, List, Optional, Sequence, Tuple, Type

from sqlalchemy import select
from sqlmodel import and_, col, select
from toolz import pipe
from toolz.curried import map

from ...core.constants import RESULT_SET_LIMIT_COUNT
from ..db_models import EmbeddableSqlModel, VectorStorage
from ..db_session import DbSession


class PostgresSession(DbSession):

    def get_embedding(self, row: EmbeddableSqlModel) -> Optional[List[float]]:
        return self.session.exec(
            select(VectorStorage.embedding_data).where(
                VectorStorage.source_id == row.id, VectorStorage.source_type == row.__class__.__name__
            )  # type: ignore
        ).first()  # type: ignore

    def get_embeddings(self, rows: Sequence[EmbeddableSqlModel]) -> List[Tuple[EmbeddableSqlModel, Optional[List[float]]]]:
        if not rows:
            return []

        # Group rows by source_type for efficiency
        rows_by_type = {}
        for row in rows:
            source_type = row.__class__.__name__
            if source_type not in rows_by_type:
                rows_by_type[source_type] = []
            rows_by_type[source_type].append(row)

        # Build conditions for all rows
        conditions = []
        for source_type, type_rows in rows_by_type.items():
            ids = [row.id for row in type_rows if row.id is not None]
            if ids:
                conditions.append(and_(VectorStorage.source_type == source_type, col(VectorStorage.source_id).in_(ids)))

        if not conditions:
            return [(row, None) for row in rows]

        # Combine all conditions with OR
        from sqlmodel import or_

        combined_condition = or_(*conditions)

        results = self.session.exec(
            select(VectorStorage.source_type, VectorStorage.source_id, VectorStorage.embedding_data).where(combined_condition)
        )

        # Create a lookup map from results
        embedding_map = {}
        for result in results:
            key = (result[0], result[1])  # (source_type, source_id)
            embedding_map[key] = result[2]

        # Return results in the same order as input
        return [(row, embedding_map.get((row.__class__.__name__, row.id))) for row in rows]

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
                source_type=row.__class__.__name__,
                source_id=row_id,
                embedding_data=embedding_data,
                embedding_text_md5=embedding_text_md5,
                user_id=row.user_id,
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
