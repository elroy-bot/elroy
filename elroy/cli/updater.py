import logging
import os
import sys

import requests
import typer
from semantic_version import Version

from .. import __version__


def check_updates():
    current_version, latest_version = check_latest_version()
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


def check_latest_version() -> tuple[Version, Version]:
    """Check latest version of elroy on PyPI
    Returns tuple of (current_version, latest_version)"""
    current_version = Version(__version__)

    try:
        response = requests.get("https://pypi.org/pypi/elroy/json")
        latest_version = Version(response.json()["info"]["version"])
        return current_version, latest_version
    except Exception as e:
        logging.warning(f"Failed to check latest version: {e}")
        return current_version, current_version
