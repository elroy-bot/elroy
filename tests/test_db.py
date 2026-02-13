import logging
import re
from re import Pattern

from sqlmodel import SQLModel

from elroy.core.ctx import ElroyContext


def test_migrations_in_sync(ctx: ElroyContext):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    db_manager = ctx.db_manager

    # Define regex patterns for tables to ignore
    ignored_table_patterns = {
        r".*vectorstorage.*",  # anything starting with vectorstorage
        r".*sqlite_.*",
        # In future: remove these:
        r".*_bkp.*",
        r".*embedding.*",
        r".*goal.*",  # temporary
        r".*message.*",
    }

    # Compile patterns for better performance
    compiled_patterns: set[Pattern] = {re.compile(pattern) for pattern in ignored_table_patterns}

    with db_manager.engine.connect() as conn:
        db_ctx = MigrationContext.configure(conn)
        diff = compare_metadata(db_ctx, SQLModel.metadata)

    # Convert all changes to strings first
    changes: list[str] = [str(change) for change in diff]

    # Filter out changes mentioning ignored tables
    filtered_changes = []
    for change in changes:
        if not any(pattern.search(change) for pattern in compiled_patterns):
            filtered_changes.append(change)
        else:
            logging.info(f"Ignoring migration: {change}")

    assert not filtered_changes, "Database migrations are not in sync with models: " + ",".join(filtered_changes)
