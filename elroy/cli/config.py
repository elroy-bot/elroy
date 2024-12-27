import contextlib
import logging
import os
from typing import Any, Generator

import typer

from ..config.ctx import ElroyContext
from ..db.db_manager import DbManager
from ..db.db_models import SYSTEM
from ..db.postgres.postgres_manager import PostgresManager
from ..db.sqlite.sqlite_manager import SqliteManager
from ..db.sqlite.utils import path_to_sqlite_url
from ..io.cli import CliIO
from ..llm.persona import get_assistant_name
from ..llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from ..messaging.context import get_refreshed_system_message
from ..repository.data_models import ContextMessage
from ..repository.goals.operations import create_onboarding_goal
from ..repository.message import replace_context_messages
from ..tools.user_preferences import set_user_preferred_name


async def onboard_user_non_interactive(ctx: ElroyContext) -> None:
    replace_context_messages(ctx, [get_refreshed_system_message(ctx, [])])


async def onboard_user_interactive(ctx: ElroyContext) -> None:
    from .chat import process_and_deliver_msg

    assert isinstance(ctx.io, CliIO)

    preferred_name = await ctx.io.prompt_user(f"Welcome! I'm an assistant named {get_assistant_name(ctx)}. What should I call you?")

    set_user_preferred_name(ctx, preferred_name)

    create_onboarding_goal(ctx, preferred_name)

    replace_context_messages(
        ctx,
        [
            get_refreshed_system_message(ctx, []),
            ContextMessage(
                role=SYSTEM,
                content=ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT(preferred_name),
                chat_model=None,
            ),
        ],
    )

    await process_and_deliver_msg(
        SYSTEM,
        ctx,
        f"User {preferred_name} has been onboarded. Say hello and introduce yourself.",
    )


@contextlib.contextmanager
def init_db(ctx: typer.Context) -> Generator[DbManager, Any, None]:

    url = ctx.params["database_url"]

    # backwards compatibility check
    if os.environ.get("ELROY_POSTGRES_URL"):
        logging.warning("ELROY_POSTGRES_URL environment variable has been renamed to ELROY_DATABASE_URL")
        url = os.environ["ELROY_POSTGRES_URL"]

    if url.startswith("postgresql://"):
        db_manager = PostgresManager
    elif url.startswith("sqlite:///"):
        db_manager = SqliteManager
    elif path_to_sqlite_url(url):
        logging.warning("SQLite URL provided without 'sqlite:///' prefix, adding it")
        url = path_to_sqlite_url(url)
        assert url
        db_manager = SqliteManager
    else:
        raise ValueError(f"Unsupported database URL: {url}. Must be either a postgresql:// or sqlite:/// URL")

    with db_manager.open_session(url, True) as db:
        yield db
