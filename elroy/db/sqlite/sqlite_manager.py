import logging
import re
import sqlite3
from pathlib import Path
from struct import unpack
from typing import Iterable, List, Optional, Tuple, Type

import sqlite_vec
from sqlalchemy import Engine, create_engine, text
from toolz import assoc, pipe
from toolz.curried import map

from ... import PACKAGE_ROOT
from ...config.constants import EMBEDDING_SIZE, RESULT_SET_LIMIT_COUNT
from ..db_manager import DbManager
from ..db_models import EmbeddableSqlModel, EmbeddableType, VectorStorage


class SqliteManager(DbManager):
    @classmethod
    def _get_config_path(cls):
        return Path(str(PACKAGE_ROOT / "db" / "sqlite" / "alembic" / "alembic.ini"))

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
                (source_type, source_id, embedding_data, embedding_text_md5)
                VALUES
                (:source_type, :source_id, :embedding_data, :embedding_text_md5)
            """
            ).bindparams(
                source_type=row.__class__.__name__,
                source_id=row_id,
                embedding_data=sqlite_vec.serialize_float32(embedding_data),
                embedding_text_md5=embedding_text_md5,
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

    def _deserialize_embedding(self, data: bytes) -> List[float]:
        """Deserialize binary vector data from SQLite into a list of floats"""
        return list(unpack(f"{EMBEDDING_SIZE}f", data))

    def query_vector(
        self, l2_distance_threshold: float, table: Type[EmbeddableSqlModel], user_id: int, query: List[float]
    ) -> Iterable[EmbeddableSqlModel]:

        # Serialize the vector once
        serialized_query = sqlite_vec.serialize_float32(query)

        # Raw SQL query
        sql = f"""
        SELECT {table.__tablename__}.*, vec_distance_L2(VectorStorage.embedding_data, ?) as distance
        FROM {table.__tablename__}
        JOIN vectorstorage ON vectorstorage.source_type = ? AND vectorstorage.source_id = {table.__tablename__}.id
        WHERE {table.__tablename__}.user_id = ?
        AND {table.__tablename__}.is_active = 1
        AND vec_distance_L2(VectorStorage.embedding_data, ?) < ?
        ORDER BY distance
        LIMIT ?
        """

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

    def find_redundant_pairs(
        self,
        table: Type[EmbeddableType],
        l2_distance_threshold: float,
        user_id: int,
        limit: int = 1,
    ) -> Iterable[Tuple[EmbeddableType, EmbeddableType]]:
        """
        Find redundant pairs of rows in the given table using vector similarity.
        """

        def _split_row_data(row_dict: dict, table: Type[EmbeddableType]) -> Tuple[dict, dict]:
            """Split a joined row into two separate dictionaries for t1 and t2"""
            # Get the column names from the table
            columns = table.model_fields.keys()

            # Split the data into t1 and t2
            t1_data = {}
            t2_data = {}

            for key, value in row_dict.items():
                if key == "distance":
                    continue
                # SQLite returns columns as "t1_column" and "t2_column"
                if key.startswith("t1_"):
                    real_key = key[3:]  # Remove 't1_' prefix
                    if real_key in columns:
                        t1_data[real_key] = value
                elif key.startswith("t2_"):
                    real_key = key[3:]  # Remove 't2_' prefix
                    if real_key in columns:
                        t2_data[real_key] = value

            return t1_data, t2_data

        results = self.session.exec(
            text(
                f"""
                WITH pairs AS (
                    SELECT
                        t1.*,
                        t2.*,
                        vec_distance_L2(v1.embedding_data, v2.embedding_data) as distance
                    FROM {table.__name__} t1
                    JOIN {table.__name__} t2 ON t1.id < t2.id
                    JOIN vectorstorage v1 ON v1.source_type = :source_type AND v1.source_id = t1.id
                    JOIN vectorstorage v2 ON v2.source_type = :source_type AND v2.source_id = t2.id
                    WHERE t1.user_id = :user_id
                    AND t2.user_id = :user_id
                    AND t1.is_active = 1
                    AND t2.is_active = 1
                    AND vec_distance_L2(v1.embedding_data, v2.embedding_data) < :threshold
                    ORDER BY RANDOM()
                    LIMIT :limit
                )
                SELECT * FROM pairs
            """
            ).bindparams(
                source_type=table.__name__, user_id=user_id, threshold=l2_distance_threshold, limit=limit
            )  # type: ignore
        )

        return pipe(
            results,
            map(lambda row: dict(row._mapping)),  # Convert SQLAlchemy Row to dict
            map(lambda d: _split_row_data(d, table)),  # Split into t1 and t2 data
            map(lambda pair: (table.model_validate(pair[0]), table.model_validate(pair[1]))),
            list,
            iter,
        )

    @property
    def vector_distance_operator(self) -> str:
        return "l2_distance"

    @classmethod
    def is_valid_url(cls, url):
        pattern = r"^sqlite:\/\/"  # Protocol
        pattern += r"(?:\/)?"  # Optional extra slash for Windows absolute paths
        pattern += r"(?:"  # Start of non-capturing group for alternatives
        pattern += r":memory:|"  # In-memory database option
        pattern += r"\/[^?]+"  # Path to database file
        pattern += r")"  # End of alternatives group
        pattern += r"(?:\?[^#]+)?$"  # Query parameters (optional)
        return bool(re.match(pattern, url))

    @classmethod
    def get_engine(cls, url: str) -> Engine:
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

        if not cls.is_valid_url(url):
            raise ValueError(f"Invalid database URL: {url}")

        return create_engine(
            url,
            creator=lambda: _sqlite_connect(url),
        )
