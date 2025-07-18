import os
import shutil
import subprocess
import sys

import requests
import typer
from semantic_version import Version

from .. import __version__
from ..core.logging import get_logger
from ..io.cli import CliIO

logger = get_logger()


def check_updates(io: CliIO):
    try:
        with io.status("Checking for updates..."):
            logger.info("Checking for updates...")
            current_version, latest_version = check_latest_version()
        if latest_version > current_version:
            if typer.confirm(f"Currently install version is {current_version}, Would you like to upgrade elroy to {latest_version}?"):
                typer.echo("Upgrading elroy...")

                # Try uv tool first
                if _is_uv_tool_installed():
                    upgrade_exit_code = _upgrade_with_uv_tool(latest_version)
                # Fall back to pip
                elif _is_pip_available():
                    upgrade_exit_code = _upgrade_with_pip(latest_version)
                else:
                    typer.echo("Error: Neither uv nor pip is available for upgrading. Please install one of them to upgrade elroy.")
                    return

                if upgrade_exit_code == 0:
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                else:
                    raise Exception("Upgrade returned nonzero exit code.")
    except requests.Timeout:
        logger.warning("Failed to check for updates: Timeout")


def _is_uv_tool_installed() -> bool:
    """Check if elroy is installed as a uv tool"""
    if not shutil.which("uv"):
        return False

    try:
        result = subprocess.run(["uv", "tool", "list"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0 and "elroy" in result.stdout
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return False


def _is_pip_available() -> bool:
    """Check if pip is available"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, timeout=5)
        return True
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return False


def _upgrade_with_uv_tool(version: Version) -> int:
    """Upgrade elroy using uv tool"""
    return os.system("uv tool upgrade elroy")


def _upgrade_with_pip(version: Version) -> int:
    """Upgrade elroy using pip"""
    return os.system(f"{sys.executable} -m pip install --upgrade --upgrade-strategy only-if-needed elroy=={version}")


def check_latest_version() -> tuple[Version, Version]:
    """Check latest version of elroy on PyPI
    Returns tuple of (current_version, latest_version)"""
    current_version = Version(__version__)

    logger.info("Checking latest version of elroy on PyPI...")

    try:
        response = requests.get("https://pypi.org/pypi/elroy/json", timeout=3)
        latest_version = Version(response.json()["info"]["version"])
        return current_version, latest_version
    except Exception as e:
        logger.warning(f"Failed to check latest version: {e}")
        return current_version, current_version
