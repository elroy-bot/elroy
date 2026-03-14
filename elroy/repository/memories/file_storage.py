"""File storage helpers for file-backed memories (Obsidian integration)."""

import json
from pathlib import Path
from typing import Any

from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import Memory
from ..file_utils import (
    read_file_text,
    read_frontmatter,
    sanitize_filename,
    update_frontmatter_fields,
)

logger = get_logger()

# Aliases kept for callers that import these names directly
read_memory_frontmatter = read_frontmatter
read_memory_text = read_file_text


def get_memory_file_path(memory_dir: Path, name: str, existing_paths: set[str]) -> Path:
    """Return a unique path for a new memory file in memory_dir."""
    base = sanitize_filename(name, fallback="memory")
    candidate = memory_dir / f"{base}.md"
    if str(candidate) not in existing_paths:
        return candidate
    counter = 2
    while True:
        candidate = memory_dir / f"{base}-{counter}.md"
        if str(candidate) not in existing_paths:
            return candidate
        counter += 1


def _build_file_content(memory_id: int, text: str) -> str:
    return f"---\nid: {memory_id}\n---\n\n{text}"


def write_memory_file(memory_dir: Path, memory: Memory, text: str, existing_paths: set[str] | None = None) -> Path:
    """Write a memory markdown file with frontmatter id. Returns the path."""
    if existing_paths is None:
        existing_paths = {str(p) for p in memory_dir.glob("*.md")}
    assert memory.id is not None
    path = get_memory_file_path(memory_dir, memory.name, existing_paths)
    path.write_text(_build_file_content(memory.id, text))
    return path


def archive_memory_file(file_path: Path, archive_dir: Path) -> Path:
    """Move a memory file to the archive directory. Returns the destination path."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / file_path.name
    # Avoid collision in archive
    if dest.exists():
        counter = 2
        stem = file_path.stem
        while dest.exists():
            dest = archive_dir / f"{stem}-{counter}.md"
            counter += 1
    file_path.rename(dest)
    return dest


def write_id_to_frontmatter(path: Path, memory_id: int) -> None:
    """Write/update the id field in the frontmatter of a markdown file."""
    update_frontmatter_fields(path, {"id": memory_id})


def _is_document_sourced(memory: Memory) -> bool:
    """Return True if any source in source_metadata is a DocumentExcerpt."""
    try:
        sources = json.loads(memory.source_metadata or "[]")
        return any(s.get("source_type") == "DocumentExcerpt" for s in sources)
    except (json.JSONDecodeError, AttributeError):
        return False


def migrate_memories_to_files(ctx: ElroyContext) -> int:
    """Migrate file-backed memories from another directory into memory_dir.

    Handles memories whose file_path is outside the current memory_dir.
    Skips memories sourced from ingested documents (DocumentExcerpt).
    Returns the count of memories migrated.
    """
    from typing import cast

    from sqlmodel import select

    memory_dir = ctx.memory_dir_path

    existing_paths: set[str] = {str(p) for p in memory_dir.glob("*.md")}

    memories = list(
        ctx.db.exec(
            select(Memory).where(
                Memory.user_id == ctx.user_id,
                cast(Any, Memory.is_active),
                Memory.file_path.is_not(None),  # type: ignore[union-attr]
            )
        ).all()
    )

    count = 0
    for memory in memories:
        if _is_document_sourced(memory):
            continue
        assert memory.id is not None
        assert memory.file_path is not None

        # Already in the right dir — nothing to do
        if Path(memory.file_path).parent.resolve() == memory_dir.resolve():
            continue

        old_path = Path(memory.file_path)
        if not old_path.exists():
            logger.warning(f"Memory {memory.id} file_path {old_path} missing, skipping dir migration")
            continue

        try:
            text = read_memory_text(old_path)
            path = write_memory_file(memory_dir, memory, text, existing_paths)
            existing_paths.add(str(path))
            memory.file_path = str(path)
            ctx.db.add(memory)
            count += 1
        except Exception as e:
            logger.error(f"Failed to migrate memory {memory.id} to file: {e}", exc_info=True)

    if count:
        ctx.db.commit()
        logger.info(f"Migrated {count} memories to files in {memory_dir}")

    return count
