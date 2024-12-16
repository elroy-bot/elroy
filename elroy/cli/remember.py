import asyncio
import sys
from datetime import datetime

import typer

from ..repository.memory import manually_record_user_memory
from ..utils.utils import datetime_to_string
from .config import cli_elroy_context, cli_elroy_context_interactive


def handle_remember(ctx: typer.Context) -> None:
    if sys.stdin.isatty():
        with cli_elroy_context_interactive(ctx) as context:
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
    else:
        with cli_elroy_context(ctx) as context:
            memory_text = sys.stdin.read()
            metadata = "Memory ingested from stdin\n" f"Ingested at: {datetime_to_string(datetime.now())}\n"
            memory_text = f"{metadata}\n{memory_text}"
            memory_name = f"Memory from stdin, ingested {datetime_to_string(datetime.now())}"
            manually_record_user_memory(context, memory_text, memory_name)
            context.io.sys_message(f"Memory created: {memory_name}")
            raise typer.Exit()
