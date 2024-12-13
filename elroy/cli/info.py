import typer

from ..config.models import get_supported_anthropic_models, get_supported_openai_models
from .updater import check_latest_version


def handle_version_check():
    current_version, latest_version = check_latest_version()
    if latest_version > current_version:
        typer.echo(f"Elroy version: {current_version} (newer version {latest_version} available)")
        typer.echo("\nTo upgrade, run:")
        typer.echo(f"    pip install --upgrade elroy=={latest_version}")
    else:
        typer.echo(f"Elroy version: {current_version} (up to date)")

    raise typer.Exit()


def handle_list_models():
    for m in get_supported_openai_models():
        print(f"{m} (OpenAI)")
    for m in get_supported_anthropic_models():
        print(f"{m} (Anthropic)")
    raise typer.Exit()
