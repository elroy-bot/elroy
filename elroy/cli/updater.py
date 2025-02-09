import asyncio
import logging
import os
import sys
from typing import Optional, Tuple

import requests
import typer
from semantic_version import Version

from .. import __version__


async def check_updates_async():
    """Non-blocking check for updates"""
    try:
        logging.debug("Checking for updates...")
        current_version, latest_version = await asyncio.to_thread(check_latest_version)
        if latest_version > current_version:
            logging.info(f"New version {latest_version} available (current: {current_version})")
            return current_version, latest_version
    except requests.Timeout:
        logging.debug("Failed to check for updates: Timeout")
    except Exception as e:
        logging.debug(f"Failed to check for updates: {e}")
    return None

def check_updates():
    """Start background update check"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.create_task(check_updates_async())

def check_latest_version() -> Tuple[Version, Version]:
    """Check latest version of elroy on PyPI
    Returns tuple of (current_version, latest_version)"""
    current_version = Version(__version__)

    logging.debug("Checking latest version of elroy on PyPI...")

    try:
        response = requests.get("https://pypi.org/pypi/elroy/json", timeout=3)
        latest_version = Version(response.json()["info"]["version"])
        return current_version, latest_version
    except Exception as e:
        logging.debug(f"Failed to check latest version: {e}")
        return current_version, current_version

def prompt_and_upgrade(current_version: Version, latest_version: Version):
    """Handle the interactive upgrade flow"""
    if typer.confirm(f"Currently installed version is {current_version}, Would you like to upgrade elroy to {latest_version}?"):
        typer.echo("Upgrading elroy...")
        upgrade_exit_code = os.system(
            f"{sys.executable} -m pip install --upgrade --upgrade-strategy only-if-needed elroy=={latest_version}"
        )

        if upgrade_exit_code == 0:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            raise Exception("Upgrade returned nonzero exit.")
