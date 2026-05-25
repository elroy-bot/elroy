import subprocess
from pathlib import Path

from ...core.constants import RecoverableToolError, tool

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

    subprocess.run(["git", "-C", str(target), "add", "."], check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-C", str(target), "commit", "-m", "Initial contrib plugin repo"],
        check=True,
        capture_output=True,
        text=True,
    )

    return (
        f"Contrib plugin repo created at {target}.\n\n"
        f"Contents:\n"
        f"  tools.py   — add @tool-decorated functions here (loaded as assistant tools)\n"
        f"  plugin.py  — define ELROY_PLUGIN here to add a sidebar tab with a custom Textual widget\n\n"
        f"Next steps:\n"
        f"1. Edit the stub files or ask me to dispatch a Codex session targeting {target}.\n"
        f"2. Set `contrib_tools_path: {target}` in your elroy config file.\n"
        f"3. Restart Elroy — tools and the plugin panel will be loaded automatically."
    )
