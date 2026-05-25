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

_EXAMPLE_TOOL_CONTENT = '''\
"""Example contrib tool. Delete this file or replace with your own tools."""
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


@tool
def create_contrib_repo(path: str) -> str:
    """Create a new contrib tools repository that Elroy can load custom tools from.

    Sets up a minimal git repository at the given path with a tools.py stub and a
    .gitignore. After creation, point elroy's `contrib_tools_path` config option at
    this directory to have Elroy automatically load any @tool-decorated functions.

    The tools.py file in the repo is auto-loaded; add additional .py files there and
    Elroy will pick them up on restart. Each tool must be a plain Python function
    decorated with @tool and imported from elroy.core.constants.

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
    tools_file = target / "tools.py"
    tools_file.write_text(_EXAMPLE_TOOL_CONTENT)

    subprocess.run(["git", "-C", str(target), "add", "."], check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-C", str(target), "commit", "-m", "Initial contrib tools repo"],
        check=True,
        capture_output=True,
        text=True,
    )

    return (
        f"Contrib tools repo created at {target}.\n\n"
        f"Next steps:\n"
        f"1. Edit {tools_file} to add your @tool-decorated functions.\n"
        f"2. Set `contrib_tools_path: {target}` in your elroy config file.\n"
        f"3. Restart Elroy — it will auto-load all @tool functions from files in that directory.\n\n"
        f"You can also ask me to dispatch a Codex session targeting {target} to have the AI write tools there directly."
    )
