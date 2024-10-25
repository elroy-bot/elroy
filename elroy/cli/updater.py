import contextlib
import logging
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
import requests
from sqlalchemy import engine_from_config
from io import StringIO
from elroy import __version__
from elroy.system.parameters import SYSTEM_MESSAGE_COLOR


import typer


import os
import sys


def _version_tuple(v: str) -> tuple:
    """Convert version string to tuple for comparison"""
    return tuple(map(int, v.split('.')))


def _upgrade_if_confirmed(current_version: str, latest_version: str) -> bool:
    """Prompt for upgrade if newer version available. Returns True if upgraded."""
    if _version_tuple(latest_version) > _version_tuple(current_version):
        if typer.confirm("Would you like to upgrade elroy?"):
            typer.echo("Upgrading elroy...")
            os.system(f"{sys.executable} -m pipx upgrade elroy=={latest_version}")
            return True
    return False


def _restart_command():
    """Restart the current command with the same arguments"""
    typer.echo("Restarting elroy...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


def _check_migrations_status(console, postgres_url: str) -> None:
    """Check if all migrations have been run.
    Returns True if migrations are up to date, False otherwise."""
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url)

    # Configure alembic logging to use Python's logging
    logging.getLogger('alembic').setLevel(logging.INFO)

    script = ScriptDirectory.from_config(config)
    engine = engine_from_config(
        config.get_section(config.config_ini_section), # type: ignore
        prefix='sqlalchemy.',
    )

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_rev = context.get_current_revision()
        head_rev = script.get_current_head()

        if current_rev != head_rev:
            with console.status(f"[{SYSTEM_MESSAGE_COLOR}] setting up database...[/]"):
                # Capture and redirect alembic output to logging

                with contextlib.redirect_stdout(StringIO()) as stdout:
                    command.upgrade(config, "head")
                    for line in stdout.getvalue().splitlines():
                        if line.strip():
                            logging.info(f"Alembic: {line.strip()}")
        else:
            logging.debug("Database is up to date.")


def _check_latest_version() -> tuple[str, str]:
    """Check latest version of elroy on PyPI
    Returns tuple of (current_version, latest_version)"""
    current_version = __version__
    try:
        response = requests.get("https://pypi.org/pypi/elroy/json")
        latest_version = response.json()["info"]["version"]
        return current_version, latest_version
    except Exception as e:
        logging.warning(f"Failed to check latest version: {e}")
        return current_version, current_version


def version_callback(value: bool):
    if value:
        current_version, latest_version = _check_latest_version()
        if _version_tuple(latest_version) > _version_tuple(current_version):
            typer.echo(f"Elroy version: {current_version} (newer version {latest_version} available)")
            typer.echo("\nTo upgrade, run:")
            typer.echo(f"    pipx upgrade elroy=={latest_version}")
        else:
            typer.echo(f"Elroy version: {current_version} (up to date)")

        raise typer.Exit()
