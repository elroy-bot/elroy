import typer

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
    from litellm import anthropic_models, open_ai_chat_completion_models

    for m in open_ai_chat_completion_models:
        print(f"{m} (OpenAI)")
    for m in anthropic_models:
        print(f"{m} (Anthropic)")
    raise typer.Exit()
