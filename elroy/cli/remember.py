import asyncio
import os
import sys
from datetime import datetime

import typer

from ..config.config import ElroyContext
from ..repository.memory import manually_record_user_memory
from ..utils.utils import datetime_to_string
from .main import get_config_typer, validate_and_configure_db


def handle_remember_file(ctx: typer.Context, file_path: str) -> None:
    validate_and_configure_db(ctx.params["postgres_url"])
    get_config_typer(ctx)

    try:
        with open(file_path, "r") as f:
            memory_text = f.read()
        # Add file metadata
        file_stat = os.stat(file_path)
        metadata = "Memory ingested from file"
        f"Created at: {datetime_to_string(datetime.fromtimestamp(file_stat.st_ctime))}"
        f"Ingested at: {datetime_to_string(datetime.now())}\n"
        memory_text = f"{memory_text}\n{metadata}"
        memory_name = f"Memory from file: {file_path}, ingested {datetime_to_string(datetime.now())}"

        manually_record_user_memory(context, memory_text, memory_name)
        context.io.sys_message(f"Memory created: {memory_name}")
        raise typer.Exit(0)
    except Exception as e:
        context.io.sys_message(f"Error reading file: {e}")
        raise typer.Exit(1)


def handle_remember_stdin(context: ElroyContext) -> None:
    memory_text = sys.stdin.read()
    metadata = "Memory ingested from stdin\n" f"Ingested at: {datetime_to_string(datetime.now())}\n"
    memory_text = f"{metadata}\n{memory_text}"
    memory_name = f"Memory from stdin, ingested {datetime_to_string(datetime.now())}"
    manually_record_user_memory(context, memory_text, memory_name)
    context.io.sys_message(f"Memory created: {memory_name}")
    raise typer.Exit()


def handle_memory_interactive(context: ElroyContext) -> None:
    memory_text = asyncio.run(context.io.prompt_user("Enter the memory text:"))
    memory_text += f"\nManually entered memory, at: {datetime_to_string(datetime.now())}"
    # Optionally get memory name
    memory_name = asyncio.run(context.io.prompt_user("Enter memory name (optional, press enter to skip):"))
    try:
        manually_record_user_memory(context, memory_text, memory_name)
        context.io.sys_message(f"Memory created: {memory_name}")
        raise typer.Exit()
    except ValueError as e:
        context.io.assistant_msg(f"Error creating memory: {e}")
        raise typer.Exit(1)
