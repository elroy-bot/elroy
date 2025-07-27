from struct import unpack
from typing import Iterable, List, Optional, Type

import sqlite_vec
from sqlalchemy import text
from toolz import assoc, pipe
from toolz.curried import map

from ...core.constants import EMBEDDING_SIZE, RESULT_SET_LIMIT_COUNT
from ..db_models import EmbeddableSqlModel, VectorStorage
from ..db_session import DbSession


class SqliteSession(DbSession):
    def get_vector_storage_row(self, row: EmbeddableSqlModel) -> Optional[VectorStorage]:
        """Get vector storage entry for a given source type and id"""
        result = self.session.exec(
            text(
                """
                SELECT * FROM vectorstorage
                WHERE source_type = :source_type AND source_id = :source_id
            """
            ).bindparams(
                source_type=row.__class__.__name__, source_id=row.id
            )  # type: ignore
        ).first()

        if result is None:
            return None

        # Convert row to VectorStorage instance
        return pipe(
            dict(result._mapping),  # Convert SQLAlchemy Row to dict
            lambda d: assoc(d, "embedding_data", self._deserialize_embedding(d["embedding_data"])),
            VectorStorage.model_validate,
        )  # type: ignore

    def update_embedding(self, vector_storage: VectorStorage, embedding: List[float], embedding_text_md5: str):
        # Use sqlite_vec's serialize_float32 to properly format the vector data
        serialized_vector = sqlite_vec.serialize_float32(embedding)

        # Use raw SQL with proper parameter binding
        self.session.exec(
            text(
                """
                UPDATE vectorstorage
                SET embedding_data = :embedding_data,
                    embedding_text_md5 = :embedding_text_md5
                WHERE source_type = :source_type
                AND source_id = :source_id
            """
            ).bindparams(
                embedding_data=serialized_vector,
                embedding_text_md5=embedding_text_md5,
                source_type=vector_storage.source_type,
                source_id=vector_storage.source_id,
            )  # type: ignore
        )
        self.session.commit()

    def insert_embedding(self, row: EmbeddableSqlModel, embedding_data, embedding_text_md5):
        # Use sqlite_vec's serialize_float32 to properly format the vector data

        row_id = row.id
        assert row_id

        self.session.exec(
            text(
                """
                INSERT INTO vectorstorage
                (source_type, source_id, embedding_data, embedding_text_md5, user_id)
                VALUES
                (:source_type, :source_id, :embedding_data, :embedding_text_md5, :user_id)
            """
            ).bindparams(
                source_type=row.__class__.__name__,
                source_id=row_id,
                embedding_data=sqlite_vec.serialize_float32(embedding_data),
                embedding_text_md5=embedding_text_md5,
                user_id=row.user_id,
            )  # type: ignore
        )
        self.session.commit()

    def get_embedding(self, row: EmbeddableSqlModel) -> Optional[List[float]]:
        result = self.session.exec(
            text(
                """
                SELECT embedding_data
                FROM vectorstorage
                WHERE source_id = :source_id
                AND source_type = :source_type
            """
            ).bindparams(
                source_id=row.id, source_type=row.__class__.__name__
            )  # type: ignore
        ).first()

        if result is None:
            return None

        # Deserialize the binary data into a list of floats
        return self._deserialize_embedding(result[0])

    def query_vector(
        self, l2_distance_threshold: float, table: Type[EmbeddableSqlModel], user_id: int, query: List[float]
    ) -> Iterable[EmbeddableSqlModel]:

        # Serialize the vector once
        serialized_query = sqlite_vec.serialize_float32(query)

        results = self.session.exec(
            text(
                f"""
                SELECT {table.__tablename__}.*, vec_distance_L2(vectorstorage.embedding_data, :query_vec) as distance
                FROM {table.__tablename__}
                JOIN vectorstorage ON vectorstorage.source_type = :source_type
                    AND vectorstorage.source_id = {table.__tablename__}.id
                WHERE {table.__tablename__}.user_id = :user_id
                AND {table.__tablename__}.is_active = 1
                AND vec_distance_L2(vectorstorage.embedding_data, :query_vec) < :threshold
                ORDER BY distance
                LIMIT :limit
            """
            ).bindparams(
                query_vec=serialized_query,
                source_type=table.__name__,
                user_id=user_id,
                threshold=l2_distance_threshold,
                limit=RESULT_SET_LIMIT_COUNT,
            )  # type: ignore
        )

        return pipe(
            results,
            map(lambda row: dict(row._mapping)),  # Convert SQLAlchemy Row to dict
            map(table.model_validate),  # Convert dict to model instance
            list,
            iter,
        )

    def _deserialize_embedding(self, data: bytes) -> List[float]:
        """Deserialize binary vector data from SQLite into a list of floats"""
        return list(unpack(f"{EMBEDDING_SIZE}f", data))
