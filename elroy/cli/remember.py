import asyncio
import sys
from datetime import datetime

import typer

from ..io.base import StdIO
from ..repository.memory import manually_record_user_memory
from ..utils.utils import datetime_to_string
from .config import (
    get_user_token,
    init_cli_io,
    init_config,
    init_db,
    init_elroy_context,
)


def handle_remember(ctx: typer.Context) -> None:
    config = init_config(ctx)
    user_token = get_user_token(ctx)
    with init_db(ctx) as db:
        if sys.stdin.isatty():
            context, new_user_created = init_elroy_context(db, init_cli_io(ctx), config, user_token)
            context.io.notify_warning("Creating memory for new user")
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
            context, new_user_created = init_elroy_context(db, StdIO(), config, user_token)
            if new_user_created:
                context.io.notify_warning("Creating memory for new user")

            memory_text = sys.stdin.read()
            metadata = "Memory ingested from stdin\n" f"Ingested at: {datetime_to_string(datetime.now())}\n"
            memory_text = f"{metadata}\n{memory_text}"
            memory_name = f"Memory from stdin, ingested {datetime_to_string(datetime.now())}"
            manually_record_user_memory(context, memory_text, memory_name)
            context.io.sys_message(f"Memory created: {memory_name}")
            raise typer.Exit()
