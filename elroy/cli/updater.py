import contextlib
import logging
import os
import sys
from io import StringIO

import requests
import typer
from semantic_version import Version
from sqlalchemy import engine_from_config

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from elroy import ROOT_DIR, __version__

from ..config.config import ElroyContext
from ..io.base import ElroyIO


def check_updates(context: ElroyContext):
    current_version, latest_version = _check_latest_version()
    if latest_version > current_version:
        if typer.confirm(f"Currently install version is {current_version}, Would you like to upgrade elroy to {latest_version}?"):
            typer.echo("Upgrading elroy...")
            try:
                os.system(f"{sys.executable} -m pip install --upgrade elroy=={latest_version}")
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as e:
                context.io.sys_message(f"Error during upgrade: {e}. Please try upgrading manually using: pipx upgrade elroy")


def ensure_current_db_migration(io: ElroyIO, postgres_url: str) -> None:
    """Check if all migrations have been run.
    Returns True if migrations are up to date, False otherwise."""
    config = Config(os.path.join(ROOT_DIR, "alembic", "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_url)

    # Configure alembic logging to use Python's logging
    logging.getLogger("alembic").setLevel(logging.INFO)

    script = ScriptDirectory.from_config(config)
    engine = engine_from_config(
        config.get_section(config.config_ini_section),  # type: ignore
        prefix="sqlalchemy.",
    )

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_rev = context.get_current_revision()
        head_rev = script.get_current_head()

        if current_rev != head_rev:
            with io.status(f"setting up database..."):
                # Capture and redirect alembic output to logging

                with contextlib.redirect_stdout(StringIO()) as stdout:
                    command.upgrade(config, "head")
                    for line in stdout.getvalue().splitlines():
                        if line.strip():
                            logging.info(f"Alembic: {line.strip()}")
        else:
            logging.debug("Database is up to date.")


def _check_latest_version() -> tuple[Version, Version]:
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


def version_callback(value: bool):
    if value:
        current_version, latest_version = _check_latest_version()
        if latest_version > current_version:
            typer.echo(f"Elroy version: {current_version} (newer version {latest_version} available)")
            typer.echo("\nTo upgrade, run:")
            typer.echo(f"    pip install --upgrade elroy=={latest_version}")
        else:
            typer.echo(f"Elroy version: {current_version} (up to date)")

        raise typer.Exit()
