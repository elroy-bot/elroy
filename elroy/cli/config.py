import contextlib
import logging
import os
from functools import partial
from typing import Any, Generator, Tuple

import typer
from toolz import pipe

from ..config.config import ElroyConfig, ElroyContext, get_config
from ..config.constants import DEFAULT_USER_TOKEN
from ..db.db_manager import DbManager
from ..db.db_models import SYSTEM
from ..db.postgres.postgres_manager import PostgresManager
from ..db.sqlite.sqlite_manager import SqliteManager
from ..db.sqlite.utils import path_to_sqlite_url
from ..io.base import IOType, StdIO
from ..io.cli import CliIO
from ..llm.persona import get_persona
from ..llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from ..logging_config import setup_logging
from ..messaging.context import get_refreshed_system_message
from ..repository.data_models import ContextMessage
from ..repository.goals.operations import create_onboarding_goal
from ..repository.message import replace_context_messages
from ..repository.user import get_or_create_user_id, get_user_id_if_exists
from ..tools.user_preferences import (
    reset_system_persona,
    set_system_persona,
    set_user_preferred_name,
)
from .updater import check_latest_version


def get_user_token(ctx: typer.Context) -> str:
    token = ctx.params["user_token"]
    assert isinstance(token, str)
    return token


def init_config(ctx: typer.Context) -> ElroyConfig:
    p = ctx.params
    chat_model = ctx.obj["chat_model"] if ctx.obj and "chat_model" in ctx.obj else p["chat_model"]
    return get_config(
        database_url=p["database_url"],
        chat_model_name=chat_model,
        debug=p["debug"],
        embedding_model=p["embedding_model"],
        embedding_model_size=p["embedding_model_size"],
        context_refresh_trigger_tokens=p["context_refresh_trigger_tokens"],
        context_refresh_target_tokens=p["context_refresh_target_tokens"],
        max_context_age_minutes=p["max_context_age_minutes"],
        context_refresh_interval_minutes=p["context_refresh_interval_minutes"],
        min_convo_age_for_greeting_minutes=p["min_convo_age_for_greeting_minutes"],
        enable_assistant_greeting=p["enable_assistant_greeting"],
        l2_memory_relevance_distance_threshold=p["l2_memory_relevance_distance_threshold"],
        l2_memory_consolidation_distance_threshold=p["l2_memory_consolidation_distance_threshold"],
        initial_context_refresh_wait_seconds=p["initial_context_refresh_wait_seconds"],
        openai_api_key=p["openai_api_key"],
        anthropic_api_key=p["anthropic_api_key"],
        openai_api_base=p["openai_api_base"],
        openai_embedding_api_base=p["openai_embedding_api_base"],
        openai_organization=p["openai_organization"],
        log_file_path=os.path.abspath(p["log_file_path"]),
        default_persona=p["default_persona"],
        enable_caching=p["enable_caching"],
    )


async def onboard_user_non_interactive(context: ElroyContext) -> None:
    replace_context_messages(context, [get_refreshed_system_message(context, [])])


async def onboard_user_interactive(context: ElroyContext[CliIO]) -> None:
    from .chat import process_and_deliver_msg

    assert isinstance(context.io, CliIO)

    preferred_name = await context.io.prompt_user("Welcome to Elroy! What should I call you?")

    set_user_preferred_name(context, preferred_name)

    create_onboarding_goal(context, preferred_name)

    replace_context_messages(
        context,
        [
            get_refreshed_system_message(context, []),
            ContextMessage(
                role=SYSTEM,
                content=ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT(preferred_name),
                chat_model=None,
            ),
        ],
    )

    await process_and_deliver_msg(
        SYSTEM,
        context,
        f"Elroy user {preferred_name} has been onboarded. Say hello and introduce yourself.",
    )


def init_cli_io(ctx: typer.Context) -> CliIO:
    return CliIO(
        show_internal_thought=ctx.params["show_internal_thought"],
        system_message_color=ctx.params["system_message_color"],
        assistant_message_color=ctx.params["assistant_color"],
        user_input_color=ctx.params["user_input_color"],
        warning_color=ctx.params["warning_color"],
        internal_thought_color=ctx.params["internal_thought_color"],
    )


def init_elroy_context(db: DbManager, io: IOType, config: ElroyConfig, user_token: str) -> Tuple[ElroyContext[IOType], bool]:
    setup_logging(config.log_file_path)

    assert isinstance(user_token, str)

    user_id, new_user_created = get_or_create_user_id(db, user_token)

    context = ElroyContext(
        db=db,
        user_id=user_id,
        config=config,
        io=io,
    )

    if not context.config.chat_model.has_tool_support:
        context.io.notify_warning(f"{context.config.chat_model.name} does not support tool calling, some functionality will be disabled.")

    if new_user_created:
        if user_token == DEFAULT_USER_TOKEN:
            logging.info(f"Initial execution, creating user for token {user_token}")
        else:
            io.notify_warning(f"New user created for token {user_token}")

    return (context, new_user_created)


def handle_show_config(ctx: typer.Context):
    config = init_config(ctx)

    for key, value in config.__dict__.items():
        print(f"{key}={value}")
    raise typer.Exit()


def handle_set_persona(ctx: typer.Context):
    config = init_config(ctx)
    user_token = ctx.params["user_token"]

    with init_db(ctx) as db:
        user_id, new_user_created = get_or_create_user_id(db, user_token)
        if new_user_created:
            logging.info(f"No user found for token {user_token}, creating one")

        context = ElroyContext(db, StdIO(), config, user_id)
        set_system_persona(context, ctx.params["set_persona"])
    raise typer.Exit()


def handle_reset_persona(ctx: typer.Context):
    config = init_config(ctx)
    user_token = ctx.params["user_token"]

    with init_db(ctx) as db:
        user_id = get_user_id_if_exists(db, user_token)
        if not user_id:
            logging.warning(f"No user found for token {user_token}, so no persona to clear")
            return typer.Exit()
        else:
            context = ElroyContext(db, StdIO(), config, user_id)
            reset_system_persona(context)
    raise typer.Exit()


def handle_show_persona(ctx: typer.Context):
    config = init_config(ctx)

    user_token = ctx.params["user_token"]

    with init_db(ctx) as db:

        pipe(
            get_user_id_if_exists(db, user_token),
            partial(get_persona, db, config),
            print,
        )
        raise typer.Exit()


def handle_list_models():
    from ..config.models import (
        get_supported_anthropic_models,
        get_supported_openai_models,
    )

    for m in get_supported_openai_models():
        print(f"{m} (OpenAI)")
    for m in get_supported_anthropic_models():
        print(f"{m} (Anthropic)")
    raise typer.Exit()


def handle_show_version():
    current_version, latest_version = check_latest_version()
    if latest_version > current_version:
        typer.echo(f"Elroy version: {current_version} (newer version {latest_version} available)")
        typer.echo("\nTo upgrade, run:")
        typer.echo(f"    pip install --upgrade elroy=={latest_version}")
    else:
        typer.echo(f"Elroy version: {current_version} (up to date)")

    raise typer.Exit()


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
