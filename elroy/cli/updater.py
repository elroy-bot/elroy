import datetime
import os
import sys
from pathlib import Path
from typing import Optional

import requests
import typer
from semantic_version import Version

from .. import __version__
from ..config.paths import get_cache_dir
from ..core.logging import get_logger
from ..io.cli import CliIO

logger = get_logger()


def get_update_check_file() -> Path:
    """Get the path to the file that stores the last update check timestamp."""
    return get_cache_dir() / "last_update_check.txt"


def get_last_update_check() -> Optional[datetime.datetime]:
    """Get the timestamp of the last successful update check.

    Returns:
        The timestamp of the last successful update check, or None if no check has been performed.
    """
    update_check_file = get_update_check_file()
    if not update_check_file.exists():
        return None

    try:
        timestamp_str = update_check_file.read_text().strip()
        return datetime.datetime.fromisoformat(timestamp_str)
    except (ValueError, IOError) as e:
        logger.warning(f"Failed to read last update check timestamp: {e}")
        return None


def set_last_update_check() -> None:
    """Set the timestamp of the last successful update check to now."""
    update_check_file = get_update_check_file()
    try:
        update_check_file.write_text(datetime.datetime.now().isoformat())
    except IOError as e:
        logger.warning(f"Failed to write last update check timestamp: {e}")


def check_updates(io: CliIO):
    # Check if we've checked for updates recently (within the last 7 days)
    last_check = get_last_update_check()
    now = datetime.datetime.now()

    if last_check and (now - last_check).days < 7:
        logger.info(f"Skipping update check - last check was {(now - last_check).days} days ago")
        return

    try:
        with io.status("Checking for updates..."):
            logger.info("Checking for updates...")
            current_version, latest_version = check_latest_version()

            # Record successful update check
            set_last_update_check()

        if latest_version > current_version:
            if typer.confirm(f"Currently install version is {current_version}, Would you like to upgrade elroy to {latest_version}?"):
                typer.echo("Upgrading elroy...")
                upgrade_exit_code = os.system(
                    f"{sys.executable} -m pip install --upgrade --upgrade-strategy only-if-needed elroy=={latest_version}"
                )

                if upgrade_exit_code == 0:
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                else:
                    raise Exception("Upgrade return nonzero exit.")
    except requests.Timeout:
        logger.warning("Failed to check for updates: Timeout")


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
