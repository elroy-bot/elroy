"""File storage helpers for agenda items."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from ...utils.clock import local_now
from ..file_utils import (
    read_file_text,
    read_frontmatter,
    sanitize_filename,
    update_frontmatter_fields,
)


def _normalize_checklist(checklist: Any) -> list[dict[str, Any]]:
    if not isinstance(checklist, list):
        return []

    normalized: list[dict[str, Any]] = []
    for raw_item in checklist:
        if not isinstance(raw_item, dict) or "id" not in raw_item or "text" not in raw_item:
            continue
        normalized.append(
            {
                "id": int(raw_item["id"]),
                "text": str(raw_item["text"]),
                "completed": bool(raw_item.get("completed", False)),
                **({"due_date": str(raw_item["due_date"])} if raw_item.get("due_date") else {}),
            }
        )
    return normalized


def _coerce_datetime(raw_value: Any) -> datetime | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, datetime):
        return raw_value
    try:
        return datetime.fromisoformat(str(raw_value))
    except ValueError:
        return None


@dataclass(frozen=True)
class AgendaFileMetadata:
    completed: bool = False
    checklist: list[dict[str, Any]] | None = None
    trigger_datetime: datetime | None = None
    trigger_context: str | None = None
    status: str | None = None
    closing_comment: str | None = None


def _build_file_content(
    text: str,
    item_date: date,
    metadata: AgendaFileMetadata | None = None,
) -> str:
    metadata = metadata or AgendaFileMetadata()
    fm: dict[str, Any] = {"date": item_date.isoformat(), "completed": metadata.completed}
    if metadata.checklist:
        fm["checklist"] = metadata.checklist
    if metadata.trigger_datetime is not None:
        fm["trigger_datetime"] = metadata.trigger_datetime
    if metadata.trigger_context:
        fm["trigger_context"] = metadata.trigger_context
    if metadata.status:
        fm["status"] = metadata.status
    if metadata.closing_comment:
        fm["closing_comment"] = metadata.closing_comment
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
    return write_agenda_item_with_metadata(agenda_dir, name, text, item_date)


def write_agenda_item_with_metadata(
    agenda_dir: Path,
    name: str,
    text: str,
    item_date: date,
    metadata: AgendaFileMetadata | None = None,
) -> Path:
    """Write a new agenda item file with optional due-item metadata. Returns the path."""
    path = get_agenda_file_path(agenda_dir, name)
    path.write_text(_build_file_content(text, item_date, metadata))
    return path


def read_agenda_metadata(path: Path) -> dict[str, Any]:
    """Return agenda frontmatter metadata."""
    return read_frontmatter(path)


def update_agenda_metadata(path: Path, updates: dict[str, Any]) -> None:
    """Update agenda item frontmatter fields."""
    update_frontmatter_fields(path, updates)


def update_agenda_body(path: Path, text: str) -> None:
    """Replace the body text of an agenda item while preserving frontmatter."""
    frontmatter = read_frontmatter(path)
    item_date_raw = frontmatter.get("date")
    parsed_date = item_date_raw if isinstance(item_date_raw, date) else date.fromisoformat(str(item_date_raw))
    path.write_text(
        _build_file_content(
            text,
            parsed_date,
            AgendaFileMetadata(
                completed=bool(frontmatter.get("completed")),
                checklist=_normalize_checklist(frontmatter.get("checklist")),
                trigger_datetime=_coerce_datetime(frontmatter.get("trigger_datetime")),
                trigger_context=(
                    str(frontmatter["trigger_context"])
                    if frontmatter.get("trigger_context")
                    else (str(frontmatter["reminder_context"]) if frontmatter.get("reminder_context") else None)
                ),
                status=str(frontmatter["status"]) if frontmatter.get("status") else None,
                closing_comment=str(frontmatter["closing_comment"]) if frontmatter.get("closing_comment") else None,
            ),
        )
    )


def mark_completed(path: Path, closing_comment: str | None = None) -> None:
    """Set completed: true in the frontmatter of an agenda item file."""
    updates: dict[str, Any] = {"completed": True, "status": "completed"}
    if closing_comment:
        updates["closing_comment"] = closing_comment
    update_frontmatter_fields(path, updates)


def find_matching_agenda_item(agenda_dir: Path, item_name: str) -> Path:
    """Find an agenda item by case-insensitive partial stem match."""
    matches = [p for p in agenda_dir.glob("*.md") if item_name.lower() in p.stem.lower()]
    if not matches:
        raise FileNotFoundError(f"No agenda item found matching '{item_name}'.")
    if len(matches) > 1:
        names = ", ".join(p.stem for p in matches)
        raise ValueError(f"Multiple agenda items match '{item_name}': {names}. Be more specific.")
    return matches[0]


def get_checklist(path: Path) -> list[dict[str, Any]]:
    """Return normalized checklist entries from an agenda item."""
    return _normalize_checklist(read_frontmatter(path).get("checklist"))


def add_checklist_item(path: Path, text: str, due_date: str | None = None) -> int:
    """Append a checklist item and return its assigned sequential id."""
    checklist = get_checklist(path)
    next_id = max((item["id"] for item in checklist), default=0) + 1
    item: dict[str, Any] = {"id": next_id, "text": text, "completed": False}
    if due_date:
        item["due_date"] = due_date
    checklist.append(item)
    update_frontmatter_fields(path, {"checklist": checklist})
    return next_id


def update_checklist_item(path: Path, item_id: int, *, text: str | None = None, completed: bool | None = None) -> dict[str, Any]:
    """Update a checklist item by id and return the updated entry."""
    checklist = get_checklist(path)
    for item in checklist:
        if item["id"] != item_id:
            continue
        if text is not None:
            item["text"] = text
        if completed is not None:
            item["completed"] = completed
        update_frontmatter_fields(path, {"checklist": checklist})
        return item
    raise LookupError(f"No checklist item with id {item_id} found.")


def _split_updates_section(body: str) -> tuple[str, str | None]:
    marker = "\n## Updates\n\n"
    if marker in body:
        main_text, updates = body.split(marker, 1)
        return main_text.rstrip(), updates.rstrip()

    stripped = body.rstrip()
    if stripped.startswith("## Updates\n"):
        return "", stripped.removeprefix("## Updates\n").strip()
    return stripped, None


def append_agenda_update(path: Path, note: str, timestamp: datetime | None = None) -> str:
    """Append a timestamped update note to the agenda item's body."""
    frontmatter = read_frontmatter(path)
    body = read_file_text(path).strip()
    main_text, updates = _split_updates_section(body)
    used_timestamp = (timestamp or local_now()).strftime("%Y-%m-%d %H:%M")
    update_line = f"- **{used_timestamp}**: {note}"

    new_body_parts = [main_text] if main_text else []
    new_updates = update_line if not updates else f"{updates}\n{update_line}"
    new_body_parts.append(f"## Updates\n\n{new_updates}")
    item_date = frontmatter.get("date")
    parsed_date = item_date if isinstance(item_date, date) else date.fromisoformat(str(item_date))
    path.write_text(
        _build_file_content(
            "\n\n".join(new_body_parts).strip(),
            parsed_date,
            AgendaFileMetadata(
                completed=bool(frontmatter.get("completed")),
                checklist=get_checklist(path),
                trigger_datetime=_coerce_datetime(frontmatter.get("trigger_datetime")),
                trigger_context=(
                    str(frontmatter["trigger_context"])
                    if frontmatter.get("trigger_context")
                    else (str(frontmatter["reminder_context"]) if frontmatter.get("reminder_context") else None)
                ),
                status=str(frontmatter["status"]) if frontmatter.get("status") else None,
                closing_comment=str(frontmatter["closing_comment"]) if frontmatter.get("closing_comment") else None,
            ),
        )
    )
    return used_timestamp


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
