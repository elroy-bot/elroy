"""File storage helpers for agenda items."""

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def sanitize_filename(name: str) -> str:
    """Replace special chars with underscores, truncate to 80 chars."""
    sanitized = re.sub(r"[^\w\s-]", "_", name)
    sanitized = re.sub(r"\s+", "_", sanitized)
    sanitized = sanitized.strip("_")
    return sanitized[:80] or "agenda_item"


def _build_file_content(text: str, item_date: date, completed: bool = False) -> str:
    fm = {"date": item_date.isoformat(), "completed": completed}
    frontmatter_str = yaml.dump(fm, default_flow_style=False).strip()
    return f"---\n{frontmatter_str}\n---\n\n{text}"


def get_agenda_file_path(agenda_dir: Path, name: str) -> Path:
    """Return a unique path for a new agenda item file."""
    base = sanitize_filename(name)
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


def read_frontmatter(path: Path) -> dict[str, Any]:
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


def read_item_text(path: Path) -> str:
    """Return the text content after frontmatter."""
    content = path.read_text()
    m = _FRONTMATTER_RE.match(content)
    if m:
        return content[m.end():].strip()
    return content.strip()


def mark_completed(path: Path) -> None:
    """Set completed: true in the frontmatter of an agenda item file."""
    content = path.read_text()
    m = _FRONTMATTER_RE.match(content)
    body = content[m.end():] if m else content
    try:
        fm: dict[str, Any] = yaml.safe_load(m.group(1)) or {} if m else {}
    except yaml.YAMLError:
        fm = {}
    fm["completed"] = True
    frontmatter_str = yaml.dump(fm, default_flow_style=False).strip()
    path.write_text(f"---\n{frontmatter_str}\n---\n\n{body.lstrip()}")


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
                if isinstance(item_date_raw, (date, datetime)):
                    item_date = item_date_raw if isinstance(item_date_raw, date) else item_date_raw.date()
                else:
                    item_date = date.fromisoformat(str(item_date_raw))
            except ValueError:
                continue
            if item_date != for_date:
                continue
        text = read_item_text(path)
        results.append((path, fm, text))
    return results
