import subprocess
from pathlib import Path

from ...config.paths import get_contrib_dir
from ...core.constants import RecoverableToolError, tool
from ...utils.git import AGENT_BRANCH

_GITIGNORE_CONTENT = """\
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
dist/
build/
"""

_EXAMPLE_TOOLS_CONTENT = '''\
"""Example contrib tools. Delete or replace with your own @tool functions."""
from elroy.core.constants import tool
from elroy.core.turn import TurnContext


@tool
def example_contrib_tool(message: str, turn: TurnContext) -> str:
    """An example contrib tool that echoes a message.

    Args:
        message: Message to echo.
        turn: Active turn context.
    """
    return f"contrib echo: {message}"
'''

_EXAMPLE_PLUGIN_CONTENT = '''\
"""Example plugin with a custom sidebar panel.

Delete this file or replace it with your own plugin. The ELROY_PLUGIN variable
tells Elroy to add a tab to the sidebar using the widget returned by widget_factory.
Textual imports must be inside widget_factory so this file can be loaded in
non-UI contexts (e.g. background workers) without pulling in Textual.
"""
from elroy.plugins.plugin import ElroyPlugin


def _make_widget():
    """Return a Textual widget for the sidebar panel."""
    from textual.app import ComposeResult
    from textual.widget import Widget
    from textual.widgets import Label

    class ExamplePanel(Widget):
        """Replace with your custom panel logic."""

        def compose(self) -> ComposeResult:
            yield Label("Hello from example plugin!\\nReplace this widget with your own.")

    return ExamplePanel()


ELROY_PLUGIN = ElroyPlugin(
    name="example_plugin",
    tab_label="Example",
    widget_factory=_make_widget,
)
'''


def _run_git(args: list[str], target: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", "-C", str(target), *args], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip() or (exc.stdout or "").strip() or str(exc)
        raise RecoverableToolError(f"git {' '.join(args)} failed in {target}: {stderr}") from exc


def _has_git_repo(target: Path) -> bool:
    return (target / ".git").exists()


def _has_commits(target: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "--verify", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _branch_exists(target: Path, branch_name: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(target), "show-ref", "--verify", f"refs/heads/{branch_name}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _current_branch(target: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(target), "branch", "--show-current"],
        check=False,
        capture_output=True,
        text=True,
    )
    branch = result.stdout.strip()
    return branch or None


def _ensure_agent_branch_checked_out(target: Path) -> None:
    if not _branch_exists(target, AGENT_BRANCH):
        _run_git(["branch", AGENT_BRANCH, "HEAD"], target)
    if _current_branch(target) != AGENT_BRANCH:
        _run_git(["checkout", AGENT_BRANCH], target)


def _write_default_contrib_files(target: Path) -> None:
    files = {
        ".gitignore": _GITIGNORE_CONTENT,
        "README.md": (
            "# Elroy Contrib\n\n"
            "Elroy loads this directory at startup. Add `@tool` functions in Python files to expose assistant tools, "
            "or define an `ELROY_PLUGIN` value with `ElroyPlugin` to add a sidebar plugin.\n"
        ),
    }
    for relative_path, content in files.items():
        path = target / relative_path
        if not path.exists():
            path.write_text(content, encoding="utf-8")


def ensure_contrib_repo(path: str | Path | None = None) -> Path:
    """Ensure the assistant-editable contrib directory exists as a git repo."""
    target = Path(path).expanduser().resolve() if path is not None else get_contrib_dir().resolve()
    target.mkdir(parents=True, exist_ok=True)

    if not _has_git_repo(target):
        _write_default_contrib_files(target)
        try:
            subprocess.run(["git", "init", str(target)], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip() or (exc.stdout or "").strip() or str(exc)
            raise RecoverableToolError(f"git init failed for {target}: {stderr}") from exc

    _run_git(["config", "user.email", "elroy-contrib@example.local"], target)
    _run_git(["config", "user.name", "Elroy Contrib"], target)

    if not _has_commits(target):
        _write_default_contrib_files(target)
        _run_git(["add", "."], target)
        _run_git(["commit", "-m", "Initial Elroy contrib repo"], target)

    _ensure_agent_branch_checked_out(target)

    return target


@tool
def create_contrib_repo(path: str) -> str:
    """Create a new contrib plugin repository that Elroy can load tools and UI panels from.

    Sets up a minimal git repository at the given path with stub files for both
    tool functions and a sidebar UI plugin. After creation, point elroy's
    ``contrib_tools_path`` config option at this directory so Elroy loads everything
    on startup.

    Each ``.py`` file (except those starting with ``_``) is scanned for:
    - Functions decorated with ``@tool`` → registered as assistant tools.
    - A module-level ``ELROY_PLUGIN`` variable (``ElroyPlugin`` instance) → adds a
      tab to the TUI sidebar with the widget returned by ``widget_factory``.

    Args:
        path: Filesystem path where the contrib repo should be created (will be created if absent).
    """
    target = Path(path).expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        raise RecoverableToolError(f"Directory {target} already exists and is non-empty. Choose an empty or non-existent path.")

    target.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(["git", "init", str(target)], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RecoverableToolError(f"git init failed: {exc.stderr.strip()}") from exc

    (target / ".gitignore").write_text(_GITIGNORE_CONTENT)
    (target / "tools.py").write_text(_EXAMPLE_TOOLS_CONTENT)
    (target / "plugin.py").write_text(_EXAMPLE_PLUGIN_CONTENT)

    _run_git(["config", "user.email", "elroy-contrib@example.local"], target)
    _run_git(["config", "user.name", "Elroy Contrib"], target)
    _run_git(["add", "."], target)
    _run_git(["commit", "-m", "Initial contrib plugin repo"], target)
    _ensure_agent_branch_checked_out(target)

    return (
        f"Contrib plugin repo created at {target}.\n\n"
        f"Contents:\n"
        f"  tools.py   — add @tool-decorated functions here (loaded as assistant tools)\n"
        f"  plugin.py  — define ELROY_PLUGIN here to add a sidebar tab with a custom Textual widget\n\n"
        f"Next steps:\n"
        f"1. Edit the stub files or ask me to use edit_contrib_with_codex for the default contrib repo.\n"
        f"2. Set `contrib_tools_path: {target}` in your elroy config file.\n"
        f"3. Restart Elroy — tools and the plugin panel will be loaded automatically."
    )
