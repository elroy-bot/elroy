import logging
import os
import platform
import shlex
import subprocess
import sys

import requests
import typer
from aider.dump import dump  # noqa: F401
from semantic_version import Version

from .. import __version__

# largely adatped from: https://github.com/Aider-AI/aider/blob/main/aider/utils.py


def printable_shell_command(cmd_list):
    """
    Convert a list of command arguments to a properly shell-escaped string.

    Args:
        cmd_list (list): List of command arguments.

    Returns:
        str: Shell-escaped command string.
    """
    if platform.system() == "Windows":
        return subprocess.list2cmdline(cmd_list)
    else:
        return shlex.join(cmd_list)


def run_install(cmd):
    print()
    print("Installing:", printable_shell_command(cmd))
    output = []

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding=sys.stdout.encoding,
            errors="replace",
        )
        print("Installing...")

        while True:
            char = process.stdout.read(1)  # type: ignore
            if not char:
                break

            output.append(char)

        return_code = process.wait()
        output = "".join(output)

        if return_code == 0:
            print("Installation complete.")
            print()
            return True, output

    except subprocess.CalledProcessError as e:
        print(f"\nError running pip install: {e}")

    print("\nInstallation failed.\n")

    return False, output


def check_updates():
    try:
        logging.info("Checking for updates...")
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
    except requests.Timeout:
        logging.warning("Failed to check for updates: Timeout")


def check_latest_version() -> tuple[Version, Version]:
    """Check latest version of elroy on PyPI
    Returns tuple of (current_version, latest_version)"""
    current_version = Version(__version__)

    logging.info("Checking latest version of elroy on PyPI...")

    try:
        response = requests.get("https://pypi.org/pypi/elroy/json", timeout=3)
        latest_version = Version(response.json()["info"]["version"])
        return current_version, latest_version
    except Exception as e:
        logging.warning(f"Failed to check latest version: {e}")
        return current_version, current_version
