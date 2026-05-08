from pathlib import Path

from pydantic import BaseModel

from ..core.constants import RecoverableToolError, tool

DEFAULT_MAX_LIST_ENTRIES = 50
DEFAULT_MAX_LIST_DEPTH = 2
DEFAULT_READ_LINE_LIMIT = 200


class PathEntry(BaseModel):
    path: str
    type: str
    size_bytes: int | None = None


class PathListing(BaseModel):
    path: str
    type: str
    recursive: bool
    max_entries: int
    max_depth: int
    truncated: bool
    entries: list[PathEntry]


class FileReadResult(BaseModel):
    path: str
    start_line: int
    end_line: int
    total_lines: int
    truncated: bool
    content: str


def _coerce_line_number(value: int | str | None, param_name: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RecoverableToolError(f"{param_name} must be an integer") from exc


def _resolve_path(path: str) -> Path:
    target = (Path.cwd() / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if not target.exists():
        raise RecoverableToolError(f"Path does not exist: {path}")
    return target


def _display_path(target: Path) -> str:
    try:
        return str(target.relative_to(Path.cwd()))
    except ValueError:
        return str(target)


def _get_entry_type(target: Path) -> str:
    if target.is_symlink():
        return "symlink"
    if target.is_dir():
        return "dir"
    return "file"


def _build_entry(target: Path) -> PathEntry:
    size_bytes = None if target.is_dir() else target.stat().st_size
    return PathEntry(path=_display_path(target), type=_get_entry_type(target), size_bytes=size_bytes)


@tool
def pwd() -> str:
    """Return the current working directory for filesystem tool calls."""
    return str(Path.cwd())


@tool
def ls(
    path: str = ".", recursive: bool = True, max_entries: int = DEFAULT_MAX_LIST_ENTRIES, max_depth: int = DEFAULT_MAX_LIST_DEPTH
) -> PathListing:
    """List a file or directory, with bounded recursive expansion for directories.

    Args:
        path: File or directory path to inspect. Relative paths are resolved from the current working directory.
        recursive: Whether to recursively expand directories.
        max_entries: Maximum number of entries to include in the listing.
        max_depth: Maximum directory depth to recurse into when recursive is true.
    """
    if max_entries < 1:
        raise RecoverableToolError("max_entries must be at least 1")
    if max_depth < 0:
        raise RecoverableToolError("max_depth must be at least 0")

    target = _resolve_path(path)
    target_type = _get_entry_type(target)
    if target_type != "dir":
        return PathListing(
            path=_display_path(target),
            type=target_type,
            recursive=False,
            max_entries=max_entries,
            max_depth=max_depth,
            truncated=False,
            entries=[_build_entry(target)],
        )

    entries: list[PathEntry] = []
    truncated = False

    def walk(directory: Path, depth: int) -> bool:
        nonlocal truncated
        children = sorted(directory.iterdir(), key=lambda child: (_get_entry_type(child) != "dir", child.name.lower(), child.name))
        for child in children:
            entries.append(_build_entry(child))
            if len(entries) >= max_entries:
                truncated = True
                return False
            if recursive and depth < max_depth and child.is_dir() and not child.is_symlink() and not walk(child, depth + 1):
                return False
        return True

    walk(target, 0)

    return PathListing(
        path=_display_path(target),
        type=target_type,
        recursive=recursive,
        max_entries=max_entries,
        max_depth=max_depth,
        truncated=truncated,
        entries=entries,
    )


@tool
def read_file(path: str, start_line: int = 1, end_line: int | None = None) -> FileReadResult:
    """Read a text file, optionally constrained to a line range.

    Args:
        path: File path to read. Relative paths are resolved from the current working directory.
        start_line: One-based starting line number to read from.
        end_line: One-based ending line number to read through. Defaults to start_line + 199.
    """
    start_line_num = _coerce_line_number(start_line, "start_line")
    end_line_num = _coerce_line_number(end_line, "end_line")
    assert start_line_num is not None

    if start_line_num < 1:
        raise RecoverableToolError("start_line must be at least 1")

    target = _resolve_path(path)
    if target.is_dir():
        raise RecoverableToolError(f"Path is a directory, not a file: {path}")

    try:
        content = target.read_text()
    except UnicodeDecodeError as exc:
        raise RecoverableToolError(f"Unable to decode file as text: {path}") from exc
    except OSError as exc:
        raise RecoverableToolError(f"Unable to read file: {path}") from exc

    lines = content.splitlines()
    total_lines = len(lines)
    if end_line_num is None:
        end_line_num = start_line_num + DEFAULT_READ_LINE_LIMIT - 1
    if end_line_num < start_line_num:
        raise RecoverableToolError("end_line must be greater than or equal to start_line")

    start_idx = start_line_num - 1
    end_idx = min(end_line_num, total_lines)
    numbered_lines = [f"{line_no}: {line}" for line_no, line in enumerate(lines[start_idx:end_idx], start=start_line_num)]
    truncated = end_idx < total_lines

    return FileReadResult(
        path=_display_path(target),
        start_line=start_line_num,
        end_line=end_idx,
        total_lines=total_lines,
        truncated=truncated,
        content="\n".join(numbered_lines),
    )
