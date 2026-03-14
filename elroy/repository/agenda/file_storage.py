"""File storage helpers for agenda items."""

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ..file_utils import (
    read_file_text,
    read_frontmatter,
    sanitize_filename,
    update_frontmatter_fields,
)


def _build_file_content(text: str, item_date: date, completed: bool = False) -> str:
    fm = {"date": item_date.isoformat(), "completed": completed}
    frontmatter_str = yaml.dump(fm, default_flow_style=False).strip()
    return f"---\n{frontmatter_str}\n---\n\n{text}"


def get_agenda_file_path(agenda_dir: Path, name: str) -> Path:
    """Return a unique path for a new agenda item file."""
    base = sanitize_filename(name, fallback="agenda_item")
    candidate = agenda_dir / f"{base}.md"
    if not candidate.exists():
        return candidate
    counter = 2
    while True:
        candidate = agenda_dir / f"{base}-{counter}.md"
        if not candidate.exists():
            return candidate
        counter += 1


def write_agenda_item(agenda_dir: Path, name: str, text: str, item_date: date) -> Path:
    """Write a new agenda item file. Returns the path."""
    path = get_agenda_file_path(agenda_dir, name)
    path.write_text(_build_file_content(text, item_date))
    return path


def mark_completed(path: Path) -> None:
    """Set completed: true in the frontmatter of an agenda item file."""
    update_frontmatter_fields(path, {"completed": True})


def list_agenda_items(agenda_dir: Path, for_date: date | None = None) -> list[tuple[Path, dict[str, Any], str]]:
    """Return list of (path, frontmatter, text) for all agenda items.

    If for_date is given, only return items matching that date.
    Items with completed=True are excluded.
    """
    results = []
    for path in sorted(agenda_dir.glob("*.md")):
        fm = read_frontmatter(path)
        if fm.get("completed"):
            continue
        if for_date is not None:
            item_date_raw = fm.get("date")
            if item_date_raw is None:
                continue
            try:
                item_date = item_date_raw if isinstance(item_date_raw, date) else date.fromisoformat(str(item_date_raw))
            except ValueError:
                continue
            if item_date != for_date:
                continue
        text = read_file_text(path).strip()
        results.append((path, fm, text))
    return results
