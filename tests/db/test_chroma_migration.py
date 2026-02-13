"""Tests for automatic SQLite -> ChromaDB migration."""

import json
import os
import sqlite3
import time
from pathlib import Path

import pytest
from sqlmodel import SQLModel

from elroy.core.constants import EMBEDDING_SIZE
from elroy.db.chroma.chroma_manager import ChromaManager
from elroy.db.chroma.migration import migrate_sqlite_vectorstorage_if_needed
from elroy.db.db_manager import get_db_manager
from elroy.db.db_models import Memory, User
from elroy.db.sqlite.sqlite_manager import SqliteManager


@pytest.fixture
def sqlite_db_url(tmp_path: Path) -> str:
    db_path = tmp_path / "elroy.db"
    return f"sqlite:///{db_path}"


def _seed_sqlite_with_embedding(sqlite_db_url: str, user_id: int = 1) -> int:
    manager = SqliteManager(sqlite_db_url)
    SQLModel.metadata.create_all(manager.engine)

    with manager.open_session() as session:
        user = User(
            id=user_id,
            token="token",
        )
        session.add(user)
        session.commit()
        created_user_id = user.id
        assert created_user_id is not None

        memory = Memory(
            user_id=created_user_id,
            name=f"Test Memory {created_user_id}",
            text=f"This is a test memory {created_user_id}",
            is_active=True,
        )
        session.add(memory)
        session.commit()
        session.refresh(memory)

        embedding = [0.1] * EMBEDDING_SIZE
        session.insert_embedding(memory, embedding, "md5")

    return created_user_id


def test_migrate_sqlite_vectors_into_empty_chroma(sqlite_db_url: str, tmp_path: Path) -> None:
    user_id = _seed_sqlite_with_embedding(sqlite_db_url)

    chroma_manager = ChromaManager(sqlite_db_url, chroma_path=tmp_path / "chroma")
    migrate_sqlite_vectorstorage_if_needed(sqlite_db_url, chroma_manager)

    collection = chroma_manager.chroma_client.get_or_create_collection(
        name=f"elroy_vectors_{user_id}",
        metadata={"hnsw:space": "l2"},
    )
    assert collection.count() == 1


def test_migration_skips_when_chroma_has_vectors(sqlite_db_url: str, tmp_path: Path) -> None:
    user_id = _seed_sqlite_with_embedding(sqlite_db_url)

    chroma_manager = ChromaManager(sqlite_db_url, chroma_path=tmp_path / "chroma")
    collection = chroma_manager.chroma_client.get_or_create_collection(
        name="elroy_vectors_999",
        metadata={"hnsw:space": "l2"},
    )
    collection.add(ids=["seed"], embeddings=[[0.0] * EMBEDDING_SIZE], metadatas=[{"source_type": "Seed"}])

    migrate_sqlite_vectorstorage_if_needed(sqlite_db_url, chroma_manager)

    assert collection.count() == 1
    assert (chroma_manager.chroma_path / "migration_state.json").exists()
    migrated_collection = chroma_manager.chroma_client.get_or_create_collection(
        name=f"elroy_vectors_{user_id}",
        metadata={"hnsw:space": "l2"},
    )
    assert migrated_collection.count() == 1


def test_auto_migration_runs_once(sqlite_db_url: str, tmp_path: Path) -> None:
    _seed_sqlite_with_embedding(sqlite_db_url)

    chroma_path = tmp_path / "chroma"
    manager = get_db_manager(sqlite_db_url, vector_backend="auto", chroma_path=chroma_path)
    assert isinstance(manager, ChromaManager)

    collection = manager.chroma_client.get_or_create_collection(
        name="elroy_vectors_1",
        metadata={"hnsw:space": "l2"},
    )
    assert collection.count() == 1

    marker = chroma_path / "migration_state.json"
    assert marker.exists()
    marker_mtime = marker.stat().st_mtime

    time.sleep(1.1)
    manager = get_db_manager(sqlite_db_url, vector_backend="auto", chroma_path=chroma_path)
    assert isinstance(manager, ChromaManager)
    assert marker.stat().st_mtime == marker_mtime


def test_migration_skips_without_vectorstorage_table(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    sqlite3.connect(db_path).close()
    sqlite_db_url = f"sqlite:///{db_path}"

    chroma_manager = ChromaManager(sqlite_db_url, chroma_path=tmp_path / "chroma")
    migrate_sqlite_vectorstorage_if_needed(sqlite_db_url, chroma_manager)

    assert not (chroma_manager.chroma_path / "migration_state.json").exists()
    assert chroma_manager.chroma_client.list_collections() == []


def test_migration_marker_is_per_database(tmp_path: Path) -> None:
    db1_url = f"sqlite:///{tmp_path / 'db1.db'}"
    db2_url = f"sqlite:///{tmp_path / 'db2.db'}"

    user_id_1 = _seed_sqlite_with_embedding(db1_url, user_id=1)
    user_id_2 = _seed_sqlite_with_embedding(db2_url, user_id=2)

    chroma_path = tmp_path / "chroma"
    chroma_manager = ChromaManager(db1_url, chroma_path=chroma_path)
    migrate_sqlite_vectorstorage_if_needed(db1_url, chroma_manager)

    chroma_manager = ChromaManager(db2_url, chroma_path=chroma_path)
    migrate_sqlite_vectorstorage_if_needed(db2_url, chroma_manager)

    marker = chroma_path / "migration_state.json"
    payload = json.loads(marker.read_text())
    assert db1_url in payload["databases"]
    assert db2_url in payload["databases"]

    collection_1 = chroma_manager.chroma_client.get_or_create_collection(
        name=f"elroy_vectors_{user_id_1}",
        metadata={"hnsw:space": "l2"},
    )
    collection_2 = chroma_manager.chroma_client.get_or_create_collection(
        name=f"elroy_vectors_{user_id_2}",
        metadata={"hnsw:space": "l2"},
    )
    assert collection_1.count() == 1
    assert collection_2.count() == 1


def test_marker_match_with_empty_chroma_reruns_migration(sqlite_db_url: str, tmp_path: Path) -> None:
    user_id = _seed_sqlite_with_embedding(sqlite_db_url)
    chroma_path = tmp_path / "chroma"
    chroma_path.mkdir(parents=True, exist_ok=True)

    db_path = Path(sqlite_db_url.replace("sqlite:///", ""))
    stat = db_path.stat()
    marker = chroma_path / "migration_state.json"
    marker.write_text(
        json.dumps(
            {
                "databases": {
                    sqlite_db_url: {
                        "database_url": sqlite_db_url,
                        "vector_count": 1,
                        "status": "complete",
                        "db_mtime": stat.st_mtime,
                        "db_size": stat.st_size,
                    }
                }
            }
        )
    )

    chroma_manager = ChromaManager(sqlite_db_url, chroma_path=chroma_path)
    migrate_sqlite_vectorstorage_if_needed(sqlite_db_url, chroma_manager)

    collection = chroma_manager.chroma_client.get_or_create_collection(
        name=f"elroy_vectors_{user_id}",
        metadata={"hnsw:space": "l2"},
    )
    assert collection.count() == 1


def test_db_change_triggers_re_migration(sqlite_db_url: str, tmp_path: Path) -> None:
    user_id = _seed_sqlite_with_embedding(sqlite_db_url)
    chroma_path = tmp_path / "chroma"

    chroma_manager = ChromaManager(sqlite_db_url, chroma_path=chroma_path)
    migrate_sqlite_vectorstorage_if_needed(sqlite_db_url, chroma_manager)

    manager = SqliteManager(sqlite_db_url)
    with manager.open_session() as session:
        memory = Memory(
            user_id=user_id,
            name="Second Memory",
            text="Second memory",
            is_active=True,
        )
        session.add(memory)
        session.commit()
        session.refresh(memory)
        embedding = [0.2] * EMBEDDING_SIZE
        session.insert_embedding(memory, embedding, "md5-2")

    db_path = Path(sqlite_db_url.replace("sqlite:///", ""))
    os.utime(db_path, None)

    migrate_sqlite_vectorstorage_if_needed(sqlite_db_url, chroma_manager)

    collection = chroma_manager.chroma_client.get_or_create_collection(
        name=f"elroy_vectors_{user_id}",
        metadata={"hnsw:space": "l2"},
    )
    assert collection.count() == 2
