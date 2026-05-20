import json
import subprocess
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from urllib.parse import unquote, urlparse

AGENT_BRANCH = "agent"


def is_running_from_source_tree() -> bool:
    current_file = Path(__file__).resolve()
    return any((parent / "pyproject.toml").is_file() for parent in current_file.parents)


def source_tree_root() -> Path | None:
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return None


def editable_install_root() -> Path | None:
    try:
        dist = distribution("elroy")
        direct_url_text = dist.read_text("direct_url.json")
    except PackageNotFoundError:
        return None

    if not direct_url_text:
        return None

    try:
        direct_url = json.loads(direct_url_text)
    except json.JSONDecodeError:
        return None

    if not direct_url.get("dir_info", {}).get("editable"):
        return None

    parsed_url = urlparse(direct_url.get("url", ""))
    if parsed_url.scheme != "file":
        return None

    return Path(unquote(parsed_url.path))


def get_current_branch(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None
