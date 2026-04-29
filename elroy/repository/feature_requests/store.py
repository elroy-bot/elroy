from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from ...config.paths import get_feature_requests_dir
from ...repository.file_utils import sanitize_filename
from ...utils.clock import utc_now


@dataclass(frozen=True)
class FeatureRequestRecord:
    path: Path
    request_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    aliases: tuple[str, ...]
    summary: str
    rationale: str | None
    supporting_context: str | None


@dataclass(frozen=True)
class FeatureRequestFrontmatter:
    request_id: str
    title: str
    status: str
    created_at: str | datetime
    updated_at: str | datetime
    aliases: list[str]


def feature_requests_dir() -> Path:
    path = get_feature_requests_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify_feature_request_title(title: str) -> str:
    return sanitize_filename(title.strip().lower().replace("_", "-").replace(" ", "-"), fallback="feature-request")


def _stringify_timestamp(value: str | datetime) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _body(summary: str, rationale: str | None, supporting_context: str | None) -> str:
    sections = ["## Summary", summary.strip()]
    if rationale:
        sections.extend(["", "## Why It Matters", rationale.strip()])
    if supporting_context:
        sections.extend(["", "## Supporting Context", supporting_context.strip()])
    return "\n".join(sections).strip() + "\n"


def build_feature_request_content(
    frontmatter: FeatureRequestFrontmatter,
    summary: str,
    rationale: str | None,
    supporting_context: str | None,
) -> str:
    frontmatter_data = {
        "id": frontmatter.request_id,
        "title": frontmatter.title,
        "status": frontmatter.status,
        "created_at": _stringify_timestamp(frontmatter.created_at),
        "updated_at": _stringify_timestamp(frontmatter.updated_at),
        "aliases": frontmatter.aliases,
    }
    frontmatter_str = yaml.safe_dump(frontmatter_data, default_flow_style=False, sort_keys=False).strip()
    return f"---\n{frontmatter_str}\n---\n\n{_body(summary, rationale, supporting_context)}"


def feature_request_path(title: str, existing_paths: set[Path] | None = None) -> Path:
    if existing_paths is None:
        existing_paths = set(feature_requests_dir().glob("*.md"))
    base = slugify_feature_request_title(title)
    candidate = feature_requests_dir() / f"{base}.md"
    if candidate not in existing_paths:
        return candidate
    counter = 2
    while True:
        candidate = feature_requests_dir() / f"{base}-{counter}.md"
        if candidate not in existing_paths:
            return candidate
        counter += 1


def write_new_feature_request(
    *,
    title: str,
    summary: str,
    rationale: str | None,
    supporting_context: str | None,
) -> FeatureRequestRecord:
    now = utc_now().isoformat()
    request_id = slugify_feature_request_title(title)
    path = feature_request_path(title)
    path.write_text(
        build_feature_request_content(
            FeatureRequestFrontmatter(
                request_id=request_id,
                title=title,
                status="open",
                created_at=now,
                updated_at=now,
                aliases=[],
            ),
            summary,
            rationale,
            supporting_context,
        ),
        encoding="utf-8",
    )
    return load_feature_request(path)


def load_feature_request(path: Path) -> FeatureRequestRecord:
    from ...repository.file_utils import read_file_text, read_frontmatter

    frontmatter = read_frontmatter(path)
    body = read_file_text(path)
    summary, rationale, supporting_context = parse_feature_request_body(body)
    aliases = tuple(str(alias) for alias in frontmatter.get("aliases", []) if str(alias).strip())
    return FeatureRequestRecord(
        path=path,
        request_id=str(frontmatter.get("id") or path.stem),
        title=str(frontmatter.get("title") or path.stem),
        status=str(frontmatter.get("status") or "open"),
        created_at=str(frontmatter.get("created_at") or ""),
        updated_at=str(frontmatter.get("updated_at") or ""),
        aliases=aliases,
        summary=summary,
        rationale=rationale,
        supporting_context=supporting_context,
    )


def parse_feature_request_body(body: str) -> tuple[str, str | None, str | None]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for line in body.splitlines():
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections.setdefault(current_section, [])
            continue
        if current_section is not None:
            sections[current_section].append(line)

    def _clean(section_name: str) -> str | None:
        value = "\n".join(sections.get(section_name, [])).strip()
        return value or None

    summary = _clean("Summary") or body.strip()
    rationale = _clean("Why It Matters")
    supporting_context = _clean("Supporting Context")
    return summary, rationale, supporting_context


def update_feature_request(
    record: FeatureRequestRecord,
    *,
    title: str | None = None,
    status: str | None = None,
    aliases: list[str] | None = None,
    summary: str | None = None,
    rationale: str | None = None,
    supporting_context: str | None = None,
) -> FeatureRequestRecord:
    updated_title = title or record.title
    updated_status = status or record.status
    updated_summary = summary or record.summary
    updated_rationale = rationale if rationale is not None else record.rationale
    updated_supporting_context = supporting_context if supporting_context is not None else record.supporting_context
    updated_aliases = aliases if aliases is not None else list(record.aliases)
    updated_at = utc_now().isoformat()
    record.path.write_text(
        build_feature_request_content(
            FeatureRequestFrontmatter(
                request_id=record.request_id,
                title=updated_title,
                status=updated_status,
                created_at=record.created_at or updated_at,
                updated_at=updated_at,
                aliases=updated_aliases,
            ),
            updated_summary,
            updated_rationale,
            updated_supporting_context,
        ),
        encoding="utf-8",
    )
    return load_feature_request(record.path)
