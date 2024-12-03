import typer

from .options import CHAT_MODEL_ALIASES
from .updater import check_latest_version


def handle_version_check(value: bool):
    if not value:
        return
    current_version, latest_version = check_latest_version()
    if latest_version > current_version:
        typer.echo(f"Elroy version: {current_version} (newer version {latest_version} available)")
        typer.echo("\nTo upgrade, run:")
        typer.echo(f"    pip install --upgrade elroy=={latest_version}")
    else:
        typer.echo(f"Elroy version: {current_version} (up to date)")

    raise typer.Exit()


def handle_list_models(value: bool):
    if not value:
        return
    alias_dict = {v.resolver(): k for k, v in CHAT_MODEL_ALIASES.items()}

    from litellm import anthropic_models, open_ai_chat_completion_models

    for m in open_ai_chat_completion_models:
        if m in alias_dict:
            print(f"{m} (OpenAI) (--{alias_dict[m]})")
        else:
            print(f"{m} (OpenAI)")
    for m in anthropic_models:
        if m in alias_dict:
            print(f"{m} (Anthropic) (--{alias_dict[m]})")
        else:
            print(f"{m} (Anthropic)")
    raise typer.Exit()
