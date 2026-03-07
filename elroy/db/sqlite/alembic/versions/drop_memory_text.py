"""drop memory text column, migrate to files

Revision ID: c9d0e1f2a3b4
Revises: b2c3d4e5f6a7
Create Date: 2026-03-07 00:00:00.000000

"""

import os
import re
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sanitize_filename(name: str) -> str:
    sanitized = re.sub(r"[^\w\s-]", "_", name)
    sanitized = re.sub(r"\s+", "_", sanitized)
    return sanitized.strip("_")[:80] or "memory"


def upgrade() -> None:
    bind = op.get_bind()

    # Migrate text-backed memories to files
    memory_dir_str = os.environ.get("ELROY_MEMORY_DIR") or str(Path.home() / ".elroy" / "memories")
    memory_dir = Path(memory_dir_str).expanduser().resolve()
    memory_dir.mkdir(parents=True, exist_ok=True)

    rows = bind.execute(sa.text("SELECT id, name, text FROM memory WHERE text IS NOT NULL AND file_path IS NULL")).fetchall()

    for row in rows:
        base = _sanitize_filename(str(row.name))
        candidate = memory_dir / f"{base}.md"
        counter = 2
        while candidate.exists():
            candidate = memory_dir / f"{base}-{counter}.md"
            counter += 1

        candidate.write_text(f"---\nid: {row.id}\n---\n\n{row.text}")
        bind.execute(sa.text("UPDATE memory SET file_path = :fp WHERE id = :id"), {"fp": str(candidate), "id": row.id})

    with op.batch_alter_table("memory") as batch_op:
        batch_op.drop_column("text")


def downgrade() -> None:
    with op.batch_alter_table("memory") as batch_op:
        batch_op.add_column(sa.Column("text", sa.Text(), nullable=True))
