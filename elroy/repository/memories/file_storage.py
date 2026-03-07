"""File storage helpers for file-backed memories (Obsidian integration)."""

import json
import re
from pathlib import Path
from typing import Any

import yaml

from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...db.db_models import Memory

logger = get_logger()

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def sanitize_filename(name: str) -> str:
    """Replace special chars with underscores, truncate to 80 chars."""
    sanitized = re.sub(r"[^\w\s-]", "_", name)
    sanitized = re.sub(r"\s+", "_", sanitized)
    sanitized = sanitized.strip("_")
    return sanitized[:80] or "memory"


def get_memory_file_path(memory_dir: Path, name: str, existing_paths: set[str]) -> Path:
    """Return a unique path for a new memory file in memory_dir."""
    base = sanitize_filename(name)
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


def read_memory_frontmatter(path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from a markdown file. Returns {} if none."""
    try:
        content = path.read_text()
    except OSError:
        return {}
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def read_memory_text(path: Path) -> str:
    """Return the text content after frontmatter."""
    content = path.read_text()
    m = _FRONTMATTER_RE.match(content)
    if m:
        return content[m.end() :]
    return content


def archive_memory_file(file_path: Path, archive_dir: Path) -> None:
    """Move a memory file to the archive directory."""
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


def write_id_to_frontmatter(path: Path, memory_id: int) -> None:
    """Write/update the id field in the frontmatter of a markdown file."""
    content = path.read_text()
    m = _FRONTMATTER_RE.match(content)
    body = content[m.end() :] if m else content
    try:
        fm: dict[str, Any] = yaml.safe_load(m.group(1)) or {} if m else {}
    except yaml.YAMLError:
        fm = {}
    fm["id"] = memory_id
    frontmatter_str = yaml.dump(fm, default_flow_style=False).strip()
    path.write_text(f"---\n{frontmatter_str}\n---\n\n{body.lstrip()}")


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
