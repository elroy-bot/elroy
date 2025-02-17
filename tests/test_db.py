import logging
import re
from typing import List, Pattern, Set

from sqlmodel import SQLModel

from elroy.db.db_manager import DbManager


def test_migrations_in_sync(db_manager: DbManager):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    # Define regex patterns for tables to ignore
    IGNORED_TABLE_PATTERNS = {
        r".*vectorstorage.*",  # anything starting with vectorstorage
        r".*sqlite_.*",
        # TODO: remove these:
        r".*_bkp.*",
        r".*embedding.*",
    }

    # Compile patterns for better performance
    compiled_patterns: Set[Pattern] = {re.compile(pattern) for pattern in IGNORED_TABLE_PATTERNS}

    with db_manager.engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        diff = compare_metadata(ctx, SQLModel.metadata)

    # Convert all changes to strings first
    changes: List[str] = [str(change) for change in diff]

    # Filter out changes mentioning ignored tables
    filtered_changes = []
    for change in changes:
        if not any(pattern.search(change) for pattern in compiled_patterns):
            filtered_changes.append(change)
        else:
            logging.warning(f"Ignoring migration: {change}")

    assert not filtered_changes, f"Database migrations are not in sync with models: " + ",".join(filtered_changes)
