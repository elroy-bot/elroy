"""Shared file-storage utilities for markdown files with YAML frontmatter."""

import re
from pathlib import Path
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def sanitize_filename(name: str, fallback: str = "item") -> str:
    """Replace special chars with underscores, truncate to 80 chars."""
    sanitized = re.sub(r"[^\w\s-]", "_", name)
    sanitized = re.sub(r"\s+", "_", sanitized)
    sanitized = sanitized.strip("_")
    return sanitized[:80] or fallback


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


def read_file_text(path: Path) -> str:
    """Return the text content after frontmatter."""
    content = path.read_text()
    m = _FRONTMATTER_RE.match(content)
    if m:
        return content[m.end() :]
    return content


def update_frontmatter_fields(path: Path, updates: dict[str, Any]) -> None:
    """Update fields in the YAML frontmatter of a markdown file."""
    content = path.read_text()
    m = _FRONTMATTER_RE.match(content)
    body = content[m.end() :] if m else content
    try:
        fm: dict[str, Any] = yaml.safe_load(m.group(1)) or {} if m else {}
    except yaml.YAMLError:
        fm = {}
    fm.update(updates)
    frontmatter_str = yaml.dump(fm, default_flow_style=False).strip()
    path.write_text(f"---\n{frontmatter_str}\n---\n\n{body.lstrip()}")
