import time
from collections.abc import Iterable
from typing import Any, cast

import chromadb
from sqlmodel import Session, col, select
from toolz import compose
from toolz.curried import do

from ..core.constants import RESULT_SET_LIMIT_COUNT
from ..core.logging import get_logger
from .db_models import EmbeddableSqlModel

logger = get_logger(__name__)


class DbSession:
    def __init__(self, url: str, session: Session, chroma_client: chromadb.ClientAPI):
        self.url = url
        self.session = session
        self.chroma_client = chroma_client
        self._collections: dict[int, chromadb.Collection] = {}

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

    def _get_collection(self, user_id: int) -> chromadb.Collection:
        if user_id not in self._collections:
            self._collections[user_id] = self.chroma_client.get_or_create_collection(
                name=f"elroy_vectors_{user_id}", metadata={"hnsw:space": "l2"}
            )
        return self._collections[user_id]

    def _doc_id(self, row: EmbeddableSqlModel) -> str:
        return f"{row.__class__.__name__}_{row.id}"

    def insert_embedding(self, row: EmbeddableSqlModel, embedding_data: list[float], embedding_text_md5: str):
        if row.id is None:
            raise ValueError("Cannot insert embedding for row without ID")
        collection = self._get_collection(row.user_id)
        collection.add(
            ids=[self._doc_id(row)],
            embeddings=[embedding_data],
            metadatas=[
                {
                    "source_type": row.__class__.__name__,
                    "source_id": row.id,
                    "user_id": row.user_id,
                    "embedding_text_md5": embedding_text_md5,
                    "is_active": bool(row.is_active) if row.is_active is not None else False,
                }
            ],
        )

    def update_embedding(self, row: EmbeddableSqlModel, embedding: list[float], embedding_text_md5: str):
        if row.id is None:
            raise ValueError("Cannot update embedding for row without ID")
        collection = self._get_collection(row.user_id)
        collection.update(
            ids=[self._doc_id(row)],
            embeddings=cast(Any, [embedding]),
            metadatas=cast(
                Any,
                [
                    {
                        "source_type": row.__class__.__name__,
                        "source_id": row.id,
                        "user_id": row.user_id,
                        "embedding_text_md5": embedding_text_md5,
                        "is_active": True,
                    }
                ],
            ),
        )

    def get_embedding(self, row: EmbeddableSqlModel) -> list[float] | None:
        if row.id is None:
            return None
        collection = self._get_collection(row.user_id)
        try:
            result = cast(dict[str, Any], collection.get(ids=[self._doc_id(row)], include=["embeddings"]))
            embeddings = result.get("embeddings")
            if embeddings is None or len(embeddings) == 0:
                return None
            return list(embeddings[0])
        except Exception as e:
            logger.warning(f"Error retrieving embedding for {self._doc_id(row)}: {e}")
            return None

    def get_embedding_text_md5(self, row: EmbeddableSqlModel) -> str | None:
        if row.id is None:
            return None
        collection = self._get_collection(row.user_id)
        try:
            result = cast(dict[str, Any], collection.get(ids=[self._doc_id(row)], include=["metadatas"]))
            metadatas = result.get("metadatas") or []
            if not metadatas:
                return None
            return str(metadatas[0].get("embedding_text_md5")) or None
        except Exception as e:
            logger.warning(f"Error retrieving embedding metadata for {self._doc_id(row)}: {e}")
            return None

    def update_embedding_active(self, row: EmbeddableSqlModel) -> None:
        if row.id is None:
            return
        collection = self._get_collection(row.user_id)
        doc_id = self._doc_id(row)
        is_active = bool(row.is_active) if row.is_active is not None else False
        try:
            result = cast(dict[str, Any], collection.get(ids=[doc_id], include=["embeddings", "metadatas"]))
        except Exception as e:
            logger.warning(f"Error retrieving embedding for {doc_id}: {e}")
            return
        if not result.get("ids"):
            return
        metadatas = result.get("metadatas") or []
        embeddings = result.get("embeddings")
        if embeddings is None or len(embeddings) == 0:
            return
        metadata = metadatas[0] if metadatas else {}
        collection.update(
            ids=[doc_id],
            embeddings=cast(Any, [embeddings[0]]),
            metadatas=cast(
                Any,
                [
                    {
                        "source_type": metadata.get("source_type", row.__class__.__name__),
                        "source_id": metadata.get("source_id", row.id),
                        "user_id": metadata.get("user_id", row.user_id),
                        "embedding_text_md5": metadata.get("embedding_text_md5"),
                        "is_active": is_active,
                    }
                ],
            ),
        )

    def query_vector(
        self, l2_distance_threshold: float, table: type[EmbeddableSqlModel], user_id: int, query: list[float]
    ) -> Iterable[EmbeddableSqlModel]:
        start_time = time.perf_counter()
        collection = self._get_collection(user_id)
        try:
            results = cast(
                dict[str, Any],
                collection.query(
                    query_embeddings=[query],
                    n_results=RESULT_SET_LIMIT_COUNT * 2,
                    where={"$and": [{"source_type": table.__name__}, {"is_active": True}]},
                    include=["metadatas", "distances"],
                ),
            )
        except Exception as e:
            logger.error(f"ChromaDB query failed for {table.__name__}: {e}")
            raise

        chroma_duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"ChromaDB vector search ({table.__name__}): {chroma_duration_ms:.0f}ms")

        processing_start = time.perf_counter()
        metadatas = results.get("metadatas") or []
        distances = results.get("distances") or []
        if not results.get("ids") or not results["ids"][0] or not metadatas or not distances:
            return iter([])

        entity_ids = [
            metadata["source_id"]
            for metadata, distance in zip(metadatas[0], distances[0], strict=False)
            if distance < l2_distance_threshold
        ]
        if not entity_ids:
            return iter([])

        entities = self.session.exec(select(table).where(col(table.id).in_(entity_ids)).where(cast(Any, table.is_active).is_(True))).all()
        entity_dict = {e.id: e for e in entities}
        sorted_entities = [entity_dict[eid] for eid in entity_ids if eid in entity_dict]

        processing_duration_ms = (time.perf_counter() - processing_start) * 1000
        logger.info(f"Result processing ({table.__name__}): {processing_duration_ms:.0f}ms - {len(sorted_entities)} results")

        return iter(sorted_entities[:RESULT_SET_LIMIT_COUNT])
