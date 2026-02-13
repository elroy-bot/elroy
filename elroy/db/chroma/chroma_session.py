"""ChromaDB-backed session for vector storage operations."""

import time
from collections.abc import Iterable
from typing import Any, cast

import chromadb
from sqlmodel import col, select

from ...core.constants import RESULT_SET_LIMIT_COUNT, allow_unused
from ...core.logging import get_logger
from ..db_models import EmbeddableSqlModel, VectorStorage
from ..db_session import DbSession

logger = get_logger(__name__)


class ChromaSession(DbSession):
    """Database session implementation using ChromaDB for vector storage.

    Architecture:
    - ChromaDB stores only vectors and metadata
    - Relational DB (SQLite/Postgres) stores entity data
    - Single collection per user: elroy_vectors_{user_id}
    - Document IDs: {source_type}_{source_id} (e.g., "Memory_123")
    - Distance metric: L2 (matching OpenAI embeddings)
    """

    def __init__(self, url: str, session, chroma_client: chromadb.ClientAPI):
        super().__init__(url, session)
        self.chroma_client = chroma_client
        self._collections: dict[int, chromadb.Collection] = {}

    def _get_collection(self, user_id: int) -> chromadb.Collection:
        """Get or create user's vector collection with L2 distance."""
        if user_id not in self._collections:
            self._collections[user_id] = self.chroma_client.get_or_create_collection(
                name=f"elroy_vectors_{user_id}", metadata={"hnsw:space": "l2"}
            )
        return self._collections[user_id]

    def _make_document_id(self, source_type: str, source_id: int) -> str:
        """Generate ChromaDB document ID from source type and ID."""
        return f"{source_type}_{source_id}"

    def get_vector_storage_row(self, row: EmbeddableSqlModel) -> VectorStorage | None:
        """Get vector storage entry for a given source type and id.

        Note: ChromaDB doesn't store VectorStorage rows, it stores embeddings directly.
        This method reconstructs a VectorStorage object from ChromaDB data for compatibility.
        """
        if row.id is None:
            return None

        collection = self._get_collection(row.user_id)
        doc_id = self._make_document_id(row.__class__.__name__, row.id)

        try:
            result = cast(dict[str, Any], collection.get(ids=[doc_id], include=["embeddings", "metadatas"]))

            if not result.get("ids"):
                return None
            embeddings = result.get("embeddings") or []
            metadatas = result.get("metadatas") or []
            if not embeddings or not metadatas:
                return None

            # Reconstruct VectorStorage from ChromaDB data
            return VectorStorage(
                id=None,  # ChromaDB doesn't use integer IDs
                source_type=row.__class__.__name__,
                source_id=row.id,
                user_id=row.user_id,
                embedding_data=list(embeddings[0]),
                embedding_text_md5=str(metadatas[0].get("embedding_text_md5", "")),
            )
        except Exception as e:
            logger.warning(f"Error retrieving vector for {doc_id}: {e}")
            return None

    def insert_embedding(self, row: EmbeddableSqlModel, embedding_data: list[float], embedding_text_md5: str):
        """Insert vector into ChromaDB with metadata."""
        if row.id is None:
            raise ValueError("Cannot insert embedding for row without ID")

        collection = self._get_collection(row.user_id)
        doc_id = self._make_document_id(row.__class__.__name__, row.id)
        is_active = bool(row.is_active) if row.is_active is not None else False

        collection.add(
            ids=[doc_id],
            embeddings=[embedding_data],
            metadatas=[
                {
                    "source_type": row.__class__.__name__,
                    "source_id": row.id,
                    "user_id": row.user_id,
                    "embedding_text_md5": embedding_text_md5,
                    "is_active": is_active,
                }
            ],
        )

    def update_embedding(self, vector_storage: VectorStorage, embedding: list[float], embedding_text_md5: str):
        """Update existing vector in ChromaDB."""
        collection = self._get_collection(vector_storage.user_id)
        doc_id = self._make_document_id(vector_storage.source_type, vector_storage.source_id)

        collection.update(
            ids=[doc_id],
            embeddings=cast(Any, [embedding]),
            metadatas=cast(
                Any,
                [
                    {
                        "source_type": vector_storage.source_type,
                        "source_id": vector_storage.source_id,
                        "user_id": vector_storage.user_id,
                        "embedding_text_md5": embedding_text_md5,
                        "is_active": True,
                    }
                ],
            ),
        )

    @allow_unused
    def upsert_embeddings(
        self,
        rows: list[EmbeddableSqlModel],
        embeddings: list[list[float]],
        embedding_text_md5s: list[str],
    ) -> None:
        """Batch upsert vectors into ChromaDB."""
        if not rows:
            return

        user_id = rows[0].user_id
        collection = self._get_collection(user_id)

        ids: list[str] = []
        metadatas: list[dict] = []
        for row, embedding_text_md5 in zip(rows, embedding_text_md5s, strict=False):
            if row.id is None:
                raise ValueError("Cannot upsert embedding for row without ID")
            is_active = bool(row.is_active) if row.is_active is not None else False
            ids.append(self._make_document_id(row.__class__.__name__, row.id))
            metadatas.append(
                {
                    "source_type": row.__class__.__name__,
                    "source_id": row.id,
                    "user_id": row.user_id,
                    "embedding_text_md5": embedding_text_md5,
                    "is_active": is_active,
                }
            )

        collection.upsert(
            ids=ids,
            embeddings=cast(Any, embeddings),
            metadatas=cast(Any, metadatas),
        )

    def update_embedding_active(self, row: EmbeddableSqlModel) -> None:
        """Update the is_active metadata in ChromaDB without re-embedding."""
        if row.id is None:
            return

        collection = self._get_collection(row.user_id)
        doc_id = self._make_document_id(row.__class__.__name__, row.id)
        is_active = bool(row.is_active) if row.is_active is not None else False

        try:
            result = cast(dict[str, Any], collection.get(ids=[doc_id], include=["embeddings", "metadatas"]))
        except Exception as e:
            logger.warning(f"Error retrieving embedding for {doc_id}: {e}")
            return

        if not result.get("ids"):
            return

        metadatas = result.get("metadatas") or []
        embeddings = result.get("embeddings") or []
        if not embeddings:
            return

        metadata = metadatas[0] if metadatas else {}
        metadata = {
            "source_type": metadata.get("source_type", row.__class__.__name__),
            "source_id": metadata.get("source_id", row.id),
            "user_id": metadata.get("user_id", row.user_id),
            "embedding_text_md5": metadata.get("embedding_text_md5"),
            "is_active": is_active,
        }

        collection.update(
            ids=[doc_id],
            embeddings=cast(Any, [embeddings[0]]),
            metadatas=cast(Any, [metadata]),
        )

    def get_embedding(self, row: EmbeddableSqlModel) -> list[float] | None:
        """Retrieve vector embedding from ChromaDB."""
        if row.id is None:
            return None

        collection = self._get_collection(row.user_id)
        doc_id = self._make_document_id(row.__class__.__name__, row.id)

        try:
            result = cast(dict[str, Any], collection.get(ids=[doc_id], include=["embeddings"]))

            if not result.get("ids"):
                return None

            embeddings = result.get("embeddings") or []
            if not embeddings:
                return None
            return list(embeddings[0])
        except Exception as e:
            logger.warning(f"Error retrieving embedding for {doc_id}: {e}")
            return None

    def get_embedding_text_md5(self, row: EmbeddableSqlModel) -> str | None:
        """Retrieve embedding text hash from ChromaDB metadata."""
        if row.id is None:
            return None

        collection = self._get_collection(row.user_id)
        doc_id = self._make_document_id(row.__class__.__name__, row.id)

        try:
            result = cast(dict[str, Any], collection.get(ids=[doc_id], include=["metadatas"]))

            if not result.get("ids"):
                return None

            metadatas = result.get("metadatas") or []
            if not metadatas:
                return None
            metadata = metadatas[0] or {}
            return str(metadata.get("embedding_text_md5"))
        except Exception as e:
            logger.warning(f"Error retrieving embedding metadata for {doc_id}: {e}")
            return None

    def query_vector(
        self, l2_distance_threshold: float, table: type[EmbeddableSqlModel], user_id: int, query: list[float]
    ) -> Iterable[EmbeddableSqlModel]:
        """Vector search with filtering, returns entity objects.

        Process:
        1. Query ChromaDB for similar vectors
        2. Filter by distance threshold and active status
        3. Extract source IDs from results
        4. Fetch full entities from relational DB
        5. Return entities in distance-sorted order
        """
        # Time the ChromaDB query execution
        start_time = time.perf_counter()

        collection = self._get_collection(user_id)

        # Query ChromaDB with metadata filters
        # Over-fetch to account for inactive records that will be filtered out
        try:
            # First, let's check what records actually exist in this collection
            logger.debug(f"Querying ChromaDB for {table.__name__} records")

            results = collection.query(
                query_embeddings=[query],
                n_results=RESULT_SET_LIMIT_COUNT * 2,
                where={"$and": [{"source_type": table.__name__}, {"is_active": True}]},
                include=["metadatas", "distances"],
            )
            results = cast(dict[str, Any], results)
        except Exception as e:
            logger.error(f"ChromaDB query failed for {table.__name__}: {e}")

            # Try to diagnose the issue by checking collection state
            try:
                collection_count = collection.count()
                logger.info(f"ChromaDB collection has {collection_count} total records")

                # Try a simpler query without filters to see if basic querying works
                test_results = collection.query(
                    query_embeddings=[query],
                    n_results=1,
                    include=["metadatas"],
                )
                logger.info(f"Basic query (no filters) returned {len(test_results['ids'][0]) if test_results['ids'] else 0} results")

                # Try querying with just the source_type filter
                type_results = collection.query(
                    query_embeddings=[query],
                    n_results=1,
                    where={"source_type": table.__name__},
                    include=["metadatas"],
                )
                logger.info(f"Query with source_type filter returned {len(type_results['ids'][0]) if type_results['ids'] else 0} results")

            except Exception as diag_error:
                logger.error(f"Diagnostic query also failed: {diag_error}")

            logger.warning("ChromaDB has inconsistent state. Re-raising exception to see full traceback.")
            # Re-raise the original exception to get full diagnostic info
            raise

        # Log ChromaDB query time
        chroma_duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"ChromaDB vector search ({table.__name__}): {chroma_duration_ms:.0f}ms")

        # Time result processing
        processing_start = time.perf_counter()

        # Filter by distance threshold and extract source_ids in order
        if not results.get("ids") or not results["ids"][0]:
            processing_duration_ms = (time.perf_counter() - processing_start) * 1000
            logger.info(f"Result processing ({table.__name__}): {processing_duration_ms:.0f}ms - no results")
            return iter([])

        metadatas = results.get("metadatas") or []
        distances = results.get("distances") or []
        if not metadatas or not distances:
            processing_duration_ms = (time.perf_counter() - processing_start) * 1000
            logger.info(f"Result processing ({table.__name__}): {processing_duration_ms:.0f}ms - missing metadata")
            return iter([])

        entity_ids = [
            metadata["source_id"]
            for metadata, distance in zip(metadatas[0], distances[0], strict=False)
            if distance < l2_distance_threshold
        ]

        if not entity_ids:
            processing_duration_ms = (time.perf_counter() - processing_start) * 1000
            logger.info(f"Result processing ({table.__name__}): {processing_duration_ms:.0f}ms - filtered out")
            return iter([])

        # Fetch entities from relational DB
        entities = self.session.exec(select(table).where(col(table.id).in_(entity_ids)).where(cast(Any, table.is_active).is_(True))).all()

        # Maintain ChromaDB's distance-sorted order
        entity_dict = {e.id: e for e in entities}
        sorted_entities = [entity_dict[eid] for eid in entity_ids if eid in entity_dict]

        processing_duration_ms = (time.perf_counter() - processing_start) * 1000
        logger.info(f"Result processing ({table.__name__}): {processing_duration_ms:.0f}ms - {len(sorted_entities)} results")

        return iter(sorted_entities[:RESULT_SET_LIMIT_COUNT])
