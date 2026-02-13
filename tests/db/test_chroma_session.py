"""Tests for ChromaDB vector storage backend."""

import tempfile
from pathlib import Path

import pytest

from elroy.db.chroma.chroma_manager import ChromaManager
from elroy.db.chroma.chroma_session import ChromaSession
from elroy.db.db_models import Memory, User


@pytest.fixture
def temp_chroma_dir():
    """Create a temporary directory for ChromaDB storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def chroma_manager(temp_chroma_dir):
    """Create a ChromaManager with temporary database."""
    # Use in-memory SQLite for relational data
    db_url = "sqlite:///:memory:"
    manager = ChromaManager(db_url, chroma_path=temp_chroma_dir)

    # Initialize database schema
    from sqlmodel import SQLModel

    SQLModel.metadata.create_all(manager.engine)

    return manager


@pytest.fixture
def test_user_id(chroma_manager):
    """Create a test user and return the user ID."""
    with chroma_manager.open_session() as session:
        user = User(
            id=1,
            token="test-token",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


class TestChromaSession:
    """Test ChromaSession vector operations."""

    def test_insert_and_get_embedding(self, chroma_manager, test_user_id):
        """Test inserting and retrieving embeddings."""
        with chroma_manager.open_session() as session:
            # Create a memory
            memory = Memory(
                user_id=test_user_id,
                name="Test Memory",
                text="This is a test memory",
                is_active=True,
            )
            session.add(memory)
            session.commit()
            session.refresh(memory)

            # Insert embedding
            embedding = [0.1, 0.2, 0.3] * 512  # 1536 dimensions
            md5_hash = "test_md5_hash"
            session.insert_embedding(memory, embedding, md5_hash)

            # Retrieve embedding
            retrieved = session.get_embedding(memory)
            assert retrieved is not None
            assert len(retrieved) == 1536
            assert list(retrieved) == pytest.approx(embedding)

            # Retrieve metadata hash
            retrieved_md5 = session.get_embedding_text_md5(memory)
            assert retrieved_md5 == md5_hash

    def test_update_embedding(self, chroma_manager, test_user_id):
        """Test updating existing embeddings."""
        with chroma_manager.open_session() as session:
            # Create and insert memory with embedding
            memory = Memory(
                user_id=test_user_id,
                name="Test Memory",
                text="Original content",
                is_active=True,
            )
            session.add(memory)
            session.commit()
            session.refresh(memory)

            original_embedding = [0.1] * 1536
            session.insert_embedding(memory, original_embedding, "md5_1")

            # Update embedding
            new_embedding = [0.9] * 1536
            vector_storage = session.get_vector_storage_row(memory)
            assert vector_storage is not None
            session.update_embedding(vector_storage, new_embedding, "md5_2")

            # Verify update
            retrieved = session.get_embedding(memory)
            assert list(retrieved) == pytest.approx(new_embedding)

    def test_query_vector_l2_distance(self, chroma_manager, test_user_id):
        """Test vector similarity search with L2 distance."""
        with chroma_manager.open_session() as session:
            # Create multiple memories with embeddings
            memories_data = [
                ("Close Match", [1.0, 0.0, 0.0] * 512),
                ("Exact Match", [0.0, 0.0, 0.0] * 512),
                ("Far Match", [10.0, 10.0, 10.0] * 512),
            ]

            for name, embedding in memories_data:
                memory = Memory(
                    user_id=test_user_id,
                    name=name,
                    text=f"Content for {name}",
                    is_active=True,
                )
                session.add(memory)
                session.commit()
                session.refresh(memory)
                session.insert_embedding(memory, embedding, f"md5_{name}")

            # Query with vector close to [0, 0, 0]
            query_vector = [0.0, 0.0, 0.0] * 512
            threshold = 600.0  # Should match "Exact Match" and "Close Match"

            results = list(session.query_vector(threshold, Memory, test_user_id, query_vector))

            # Verify results
            assert len(results) >= 2  # At least Exact and Close Match
            result_names = [m.name for m in results]
            assert "Exact Match" in result_names
            assert "Close Match" in result_names

    def test_query_vector_filters_inactive(self, chroma_manager, test_user_id):
        """Test that query_vector respects is_active filter."""
        with chroma_manager.open_session() as session:
            # Create active and inactive memories
            active_memory = Memory(
                user_id=test_user_id,
                name="Active Memory",
                text="Active",
                is_active=True,
            )
            inactive_memory = Memory(
                user_id=test_user_id,
                name="Inactive Memory",
                text="Inactive",
                is_active=False,
            )

            session.add(active_memory)
            session.add(inactive_memory)
            session.commit()
            session.refresh(active_memory)
            session.refresh(inactive_memory)

            # Insert same embedding for both
            embedding = [1.0] * 1536
            session.insert_embedding(active_memory, embedding, "md5_active")
            session.insert_embedding(inactive_memory, embedding, "md5_inactive")

            # Query should only return active memory
            results = list(session.query_vector(10.0, Memory, test_user_id, embedding))

            assert len(results) == 1
            assert results[0].name == "Active Memory"

    def test_query_vector_respects_user_id(self, chroma_manager):
        """Test that vector search respects user_id isolation."""
        with chroma_manager.open_session() as session:
            # Create two users
            user1 = User(id=1, token="token-1")
            user2 = User(id=2, token="token-2")
            session.add(user1)
            session.add(user2)
            session.commit()

            # Create memories for each user with same embedding
            embedding = [1.0] * 1536

            assert user1.id is not None
            assert user2.id is not None
            user1_id = user1.id
            user2_id = user2.id

            memory1 = Memory(user_id=user1_id, name="User 1 Memory", text="Content 1", is_active=True)
            memory2 = Memory(user_id=user2_id, name="User 2 Memory", text="Content 2", is_active=True)

            session.add(memory1)
            session.add(memory2)
            session.commit()
            session.refresh(memory1)
            session.refresh(memory2)

            session.insert_embedding(memory1, embedding, "md5_1")
            session.insert_embedding(memory2, embedding, "md5_2")

            # Query for user1 should only return user1's memory
            results = list(session.query_vector(10.0, Memory, user1_id, embedding))

            assert len(results) == 1
            assert results[0].user_id == user1_id
            assert results[0].name == "User 1 Memory"


class TestChromaManager:
    """Test ChromaManager initialization and lifecycle."""

    def test_manager_initialization(self, temp_chroma_dir):
        """Test ChromaManager initializes correctly."""
        manager = ChromaManager("sqlite:///:memory:", chroma_path=temp_chroma_dir)

        assert manager.url == "sqlite:///:memory:"
        assert manager.chroma_path == temp_chroma_dir
        assert manager.session_class == ChromaSession

    def test_chroma_client_persistence(self, temp_chroma_dir):
        """Test ChromaDB client uses persistent storage."""
        manager = ChromaManager("sqlite:///:memory:", chroma_path=temp_chroma_dir)

        # Access chroma_client to trigger initialization
        _ = manager.chroma_client

        # Verify persistence directory was created
        assert temp_chroma_dir.exists()
        assert (temp_chroma_dir / "chroma.sqlite3").exists()

    def test_open_session_returns_chroma_session(self, chroma_manager):
        """Test that open_session returns ChromaSession instance."""
        with chroma_manager.open_session() as session:
            assert isinstance(session, ChromaSession)
            assert hasattr(session, "chroma_client")

    def test_connection_check(self, temp_chroma_dir):
        """Test connection check validates both databases."""
        manager = ChromaManager("sqlite:///:memory:", chroma_path=temp_chroma_dir)

        # Initialize schema
        from sqlmodel import SQLModel

        SQLModel.metadata.create_all(manager.engine)

        # Should not raise
        manager.check_connection()


@pytest.mark.integration
class TestBackendParity:
    """Test that ChromaDB backend returns same results as SQLite backend."""

    def test_same_query_results(self):
        """Test that both backends return identical results for same query.

        This is a placeholder for integration tests that would:
        1. Create identical data in both SQLite and ChromaDB
        2. Run same queries on both backends
        3. Verify results match (within floating point precision)
        """
        pytest.skip("Integration test - requires both backends initialized")  # type: ignore
