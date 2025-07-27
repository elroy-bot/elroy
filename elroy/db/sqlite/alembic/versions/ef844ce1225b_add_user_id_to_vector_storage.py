"""add_user_id_to_vector_storage

Revision ID: ef844ce1225b
Revises: 9eb7c341e950
Create Date: 2025-07-27 12:40:54.080721

"""

import logging
from typing import Sequence, Union

import sqlite_vec
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ef844ce1225b"
down_revision: Union[str, None] = "9eb7c341e950"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable user_id column to vectorstorage table
    connection = op.get_bind().connection

    try:

        connection.enable_load_extension(True)  # type: ignore
        sqlite_vec.load(connection)  # type: ignore
        connection.enable_load_extension(False)  # type: ignore
    except Exception as e:
        logging.error(f"Failed to load sqlite_vec extension: {e}")
        raise

    logging.debug("Attempting to create vectorstorage table...")

    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS vectorstorage_bkp USING vec0(
            id INTEGER PRIMARY KEY,  -- This aliases rowid
            source_type TEXT,
            source_id INTEGER,
            embedding_data FLOAT[1536],
            embedding_text_md5 TEXT
        )
    """
    )

    op.execute(
        """
    INSERT INTO vectorstorage_bkp SELECT * FROM vectorstorage
    """
    )

    op.execute(
        """
    DROP TABLE vectorstorage
    """
    )

    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS vectorstorage USING vec0(
            id INTEGER PRIMARY KEY,  -- This aliases rowid
            source_type TEXT,
            source_id INTEGER,
            user_id INTEGER,
            embedding_data FLOAT[1536],
            embedding_text_md5 TEXT
            )
    """
    )

    op.execute(
        """
        INSERT INTO vectorstorage (id, source_type, source_id, embedding_data, embedding_text_md5, user_id) SELECT
        v.id,
        v.source_type,
        v.source_id,
        v.embedding_data,
        v.embedding_text_md5,
        t.user_id
        FROM vectorstorage_bkp v
        JOIN goal t
        ON v.source_type = 'Goal' and v.source_id = t.id
        """
    )

    op.execute(
        """
        INSERT INTO vectorstorage (id, source_type, source_id, embedding_data, embedding_text_md5, user_id) SELECT
        v.id,
        v.source_type,
        v.source_id,
        v.embedding_data,
        v.embedding_text_md5,
        t.user_id
        FROM vectorstorage_bkp v
        JOIN memory t
        ON v.source_type = 'Memory' and v.source_id = t.id
        """
    )

    op.execute(
        """
        INSERT INTO vectorstorage (id, source_type, source_id, embedding_data, embedding_text_md5, user_id) SELECT
        v.id,
        v.source_type,
        v.source_id,
        v.embedding_data,
        v.embedding_text_md5,
        t.user_id
        FROM vectorstorage_bkp v
        JOIN documentexcerpt t
        ON v.source_type = 'DocumentExcerpt' and v.source_id = t.id
        """
    )


def downgrade() -> None:
    # Remove user_id column from vectorstorage table
    op.drop_column("vectorstorage", "user_id")
