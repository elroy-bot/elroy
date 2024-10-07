import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List

import typer
from colorama import Fore, init
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from pygments.lexers.special import TextLexer
from rich.console import Console
from rich.panel import Panel
from sqlmodel import Session
from toolz import concat, pipe, unique
from toolz.curried import filter, map, remove

from alembic import command
from alembic.config import Config
from elroy.config import get_config, session_manager
from elroy.memory.system_context import context_refresh_if_needed
from elroy.onboard_user import onboard_user
from elroy.store.data_models import ArchivalMemory, Goal
from elroy.store.message import get_context_messages
from elroy.store.user import is_user_exists
from elroy.system.parameters import CLI_USER_ID
from elroy.tools.functions.user_preferences import set_user_preferred_name
from elroy.tools.messenger import process_message

app = typer.Typer()

def print_goal(db_session: Session, goal_id: int) -> str:
    """Print the text of a goal"""
    goal = db_session.get(Goal, goal_id)
    if goal:
        return f"Goal: {goal.name}\n\nDescription: {goal.description}"
    else:
        return f"Goal with ID {goal_id} not found."


def get_relevant_memories(session: Session, user_id: int) -> List[str]:
    return pipe(
        get_context_messages(session, user_id),
        map(lambda m: m.memory_metadata),
        filter(lambda m: m is not None),
        concat,
        remove(lambda m: m.memory_type == ArchivalMemory.__name__),
        map(lambda m: f"{m.memory_type}: {m.name}"),
        unique,
        list,
    )  # type: ignore


def hex_to_ansi(hex_color):
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return f"\033[38;2;{r};{g};{b}m"


RESET_COLOR = Fore.RESET
DEFAULT_OUTPUT_COLOR = hex_to_ansi("#77DFD8")
DEFAULT_INPUT_COLOR = "#FFE377"
RESET_COLOR = "\033[0m"


def exit_cli():
    print("Exiting...")
    exit()


def rule():
    console = Console()
    console.rule(style=DEFAULT_INPUT_COLOR)


def display_memory_titles(titles):
    console = Console()
    if titles:
        panel = Panel("\n".join(titles), title="Relevant Memories", expand=False, border_style=DEFAULT_INPUT_COLOR)
        console.print(panel)


async def async_context_refresh_if_needed(session, trigger_limit, target, user_id):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, context_refresh_if_needed, session, trigger_limit, target, user_id)


@app.command()
def chat():
    """Start the Elroy chat interface"""
    asyncio.run(main_chat())


async def main_chat():
    init(autoreset=True)

    console = Console()
    history = InMemoryHistory()

    style = Style.from_dict(
        {
            "prompt": "bold",
            "user-input": DEFAULT_INPUT_COLOR + " bold",
            "": DEFAULT_INPUT_COLOR,
            "pygments.literal.string": f"bold italic {DEFAULT_INPUT_COLOR}",
        }
    )
    session = PromptSession(
        history=history,
        style=style,
        lexer=PygmentsLexer(TextLexer),
    )

    config = get_config()

    with session_manager() as db_session:

        def process_and_deliver_msg(user_input):
            if user_input.startswith("/print_goal"):
                try:
                    _, goal_id = user_input.split()
                    response = print_goal(db_session, int(goal_id))
                except ValueError:
                    response = "Invalid goal ID. Usage: /print_goal <goal_id>"
            else:
                response = process_message(db_session, CLI_USER_ID, user_input)
            print(f"{DEFAULT_OUTPUT_COLOR}{response}{RESET_COLOR}")

        if not is_user_exists(db_session, CLI_USER_ID):
            name = await session.prompt_async(HTML("<b>Welcome to Elroy! What should I call you? </b>"), style=style)
            user_id = onboard_user(db_session, name)
            assert isinstance(user_id, int)

            set_user_preferred_name(db_session, user_id, name)
            msg = f"[This is a hidden system message. Elroy user {name} has been onboarded. Say hello and introduce yourself.]"
            process_and_deliver_msg(msg)

        while True:
            try:
                rule()

                # Fetch and display relevant memories
                relevant_memories = get_relevant_memories(db_session, CLI_USER_ID)
                if relevant_memories:
                    display_memory_titles(relevant_memories)

                user_input = await session.prompt_async(HTML("<b>> </b>"), style=style)
                if user_input.lower().startswith("/exit") or user_input == "exit":
                    exit_cli()
                elif user_input:
                    process_and_deliver_msg(user_input)
                    # Start context refresh asynchronously
                    asyncio.create_task(
                        async_context_refresh_if_needed(
                            db_session, config.context_refresh_token_trigger_limit, config.context_refresh_token_target, CLI_USER_ID
                        )
                    )
            except KeyboardInterrupt:
                console.clear()
                continue
            except EOFError:
                exit_cli()


@app.command()
def upgrade():
    """Run Alembic database migrations"""
    config = get_config()
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", config.database_url)
    command.upgrade(alembic_cfg, "head")
    typer.echo("Database upgrade completed.")


def main():
    app()


if __name__ == "__main__":
    main()

