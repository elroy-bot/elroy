"""Utilities to migrate SQLite vectorstorage data into ChromaDB."""

import json
import sqlite3
from pathlib import Path
from struct import unpack
from urllib.parse import urlparse

from ...core.constants import EMBEDDING_SIZE
from ...core.logging import get_logger
from .chroma_manager import ChromaManager

logger = get_logger(__name__)

_MIGRATION_MARKER = "migration_state.json"
_MARKER_KEY = "databases"


def _marker_path(chroma_manager: ChromaManager) -> Path:
    return chroma_manager.chroma_path / _MIGRATION_MARKER


def _read_marker(chroma_manager: ChromaManager) -> dict:
    path = _marker_path(chroma_manager)
    if not path.exists():
        return {_MARKER_KEY: {}}
    try:
        payload = json.loads(path.read_text())
        if _MARKER_KEY not in payload:
            payload[_MARKER_KEY] = {}
        return payload
    except Exception as exc:
        logger.warning(f"Failed to read Chroma migration marker: {exc}")
        return {_MARKER_KEY: {}}


def _write_marker(chroma_manager: ChromaManager, database_url: str, vector_count: int, db_stats: dict) -> None:
    path = _marker_path(chroma_manager)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _read_marker(chroma_manager)
    payload[_MARKER_KEY][database_url] = {
        "database_url": database_url,
        "vector_count": vector_count,
        "status": "complete",
        **db_stats,
    }
    path.write_text(json.dumps(payload))


def _sqlite_db_path(database_url: str) -> Path | None:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        return None
    if parsed.path in ("/:memory:", ":memory:"):
        return None
    if not parsed.path:
        return None
    path = parsed.path
    if path.startswith("//"):
        path = path[1:]
    return Path(path)


def _get_sqlite_db_stats(database_url: str) -> dict:
    db_path = _sqlite_db_path(database_url)
    if not db_path or not db_path.exists():
        return {"db_mtime": None, "db_size": None}
    stat = db_path.stat()
    return {"db_mtime": stat.st_mtime, "db_size": stat.st_size}


def _get_sqlite_vector_count(database_url: str) -> int | None:
    db_path = _sqlite_db_path(database_url)
    if not db_path:
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            result = conn.execute("SELECT COUNT(*) FROM vectorstorage").fetchone()
    except Exception as exc:  # sqlite3.OperationalError or table missing
        logger.info(f"Skipping Chroma migration; vectorstorage not available: {exc}")
        return None

    if result is None:
        return 0

    return result[0]


def _chroma_has_vectors(chroma_manager: ChromaManager) -> bool:
    try:
        collections = chroma_manager.chroma_client.list_collections()
    except Exception as exc:
        logger.warning(f"Failed to list ChromaDB collections: {exc}")
        return False

    for collection in collections:
        try:
            if collection.count() > 0:
                return True
        except Exception:
            continue

    return False


def migrate_sqlite_vectorstorage_if_needed(database_url: str, chroma_manager: ChromaManager) -> None:
    """Migrate embeddings from sqlite-vec into ChromaDB when Chroma is empty."""
    db_stats = _get_sqlite_db_stats(database_url)
    marker = _read_marker(chroma_manager)
    marker_entry = marker[_MARKER_KEY].get(database_url)
    marker_matches = (
        marker_entry
        and marker_entry.get("status") == "complete"
        and marker_entry.get("db_mtime") == db_stats["db_mtime"]
        and marker_entry.get("db_size") == db_stats["db_size"]
    )
    if marker_matches:
        if _chroma_has_vectors(chroma_manager):
            logger.info("Chroma migration already completed; skipping.")
            return
        logger.warning("Chroma migration marker found but no vectors detected; re-running migration.")

    vector_count = _get_sqlite_vector_count(database_url)
    if vector_count is None or vector_count == 0:
        return

    if _chroma_has_vectors(chroma_manager):
        _write_marker(chroma_manager, database_url, vector_count, db_stats)
        # If no marker match, we still migrate to be safe (idempotent upsert).
        if not marker_matches:
            logger.info("Chroma already has vectors but no matching migration marker; running migration anyway.")
        else:
            return

    logger.info(f"Starting Chroma migration for {vector_count} embeddings from sqlite-vec")

    batch_size = 500
    batch_embeddings = []
    batch_ids = []
    batch_metadatas = []
    current_user_id = None

    def flush_batches(user_id: int) -> None:
        if not batch_ids:
            return
        collection = chroma_manager.chroma_client.get_or_create_collection(
            name=f"elroy_vectors_{user_id}",
            metadata={"hnsw:space": "l2"},
        )
        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            metadatas=batch_metadatas,
        )

    db_path = _sqlite_db_path(database_url)
    if not db_path:
        return
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT source_type, source_id, user_id, embedding_data, embedding_text_md5
            FROM vectorstorage
            ORDER BY user_id
            """
        )

        for row in rows:
            source_type, source_id, user_id, embedding_data, embedding_text_md5 = row

            if current_user_id is None:
                current_user_id = user_id
            elif user_id != current_user_id:
                flush_batches(current_user_id)
                batch_embeddings.clear()
                batch_ids.clear()
                batch_metadatas.clear()
                current_user_id = user_id

            if embedding_data is None or embedding_text_md5 is None:
                continue

            if isinstance(embedding_data, memoryview):
                embedding_data = embedding_data.tobytes()

            embedding = list(unpack(f"{EMBEDDING_SIZE}f", embedding_data))
            doc_id = f"{source_type}_{source_id}"

            batch_ids.append(doc_id)
            batch_embeddings.append(embedding)
            batch_metadatas.append(
                {
                    "source_type": source_type,
                    "source_id": source_id,
                    "user_id": user_id,
                    "embedding_text_md5": embedding_text_md5,
                    "is_active": True,
                }
            )

            if len(batch_ids) >= batch_size:
                flush_batches(user_id)
                batch_embeddings.clear()
                batch_ids.clear()
                batch_metadatas.clear()

    if current_user_id is not None:
        flush_batches(current_user_id)

    _write_marker(chroma_manager, database_url, vector_count, db_stats)
    logger.info("Chroma migration completed")
