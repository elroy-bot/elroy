import asyncio
import contextlib
import logging
import os
from functools import partial
from io import StringIO
from typing import Optional

import typer
from sqlalchemy import create_engine, engine_from_config
from sqlmodel import Session, text
from toolz import pipe

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from ..config.config import (
    ROOT_DIR,
    ElroyConfig,
    ElroyContext,
    get_config,
    session_manager,
)
from ..io.base import ElroyIO, StdIO
from ..io.cli import CliIO
from ..llm.persona import get_persona
from ..llm.prompts import ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT
from ..logging_config import setup_logging
from ..messaging.context import get_refreshed_system_message
from ..repository.data_models import SYSTEM, ContextMessage
from ..repository.goals.operations import create_onboarding_goal
from ..repository.message import replace_context_messages
from ..repository.user import create_user_id, get_user_id_if_exists
from ..tools.user_preferences import (
    reset_system_persona,
    set_system_persona,
    set_user_preferred_name,
)
from .updater import check_latest_version


def init_config(ctx: typer.Context) -> ElroyConfig:
    p = ctx.params
    chat_model = ctx.obj["chat_model"] if ctx.obj and "chat_model" in ctx.obj else p["chat_model"]
    return get_config(
        postgres_url=p["postgres_url"],
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


def onboard_user(context: ElroyContext) -> None:
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


@contextlib.contextmanager
def cli_elroy_context_interactive(ctx: typer.Context):
    config = init_config(ctx)
    setup_logging(config.log_file_path)
    validate_and_configure_db(config.postgres_url)
    io = CliIO(
        show_internal_thought=ctx.params["show_internal_thought"],
        system_message_color=ctx.params["system_message_color"],
        assistant_message_color=ctx.params["assistant_color"],
        user_input_color=ctx.params["user_input_color"],
        warning_color=ctx.params["warning_color"],
        internal_thought_color=ctx.params["internal_thought_color"],
    )

    with Session(create_engine(config.postgres_url)) as session:
        user_token = ctx.params["user_token"]
        assert isinstance(user_token, str)

        user_id = get_user_id_if_exists(session, user_token)

        if not user_id:
            user_id = create_user_id(session, user_token)
            new_user_created = True
        else:
            new_user_created = False

        context = ElroyContext(
            user_id=user_id,
            session=session,
            config=config,
            io=io,
        )

        if new_user_created:
            context.io.notify_warning("Elroy is in alpha release")
            asyncio.run(onboard_user_interactive(context))

        if not context.config.chat_model.has_tool_support:
            context.io.notify_warning(
                f"{context.config.chat_model.name} does not support tool calling, some functionality will be disabled."
            )

        yield context


@contextlib.contextmanager
def cli_elroy_context(ctx: typer.Context):
    config = init_config(ctx)
    with session_manager(config.postgres_url) as session:
        with init_elroy_context(session, config, StdIO(), ctx.params["user_token"]) as context:
            yield context


@contextlib.contextmanager
def init_elroy_context(session: Session, config: ElroyConfig, io: ElroyIO, user_token: str):
    setup_logging(config.log_file_path)
    validate_and_configure_db(config.postgres_url)

    with Session(create_engine(config.postgres_url)) as session:
        assert isinstance(user_token, str)

        user_id = get_user_id_if_exists(session, user_token)
        if not user_id:
            user_id = create_user_id(session, user_token)
            new_user_created = True
        else:
            new_user_created = False

        context = ElroyContext(
            user_id=user_id,
            session=session,
            config=config,
            io=io,
        )

        if new_user_created:
            onboard_user(context)
        yield context


def handle_show_config(ctx: typer.Context):
    config = init_config(ctx)

    for key, value in config.__dict__.items():
        print(f"{key}={value}")
    raise typer.Exit()


def handle_set_persona(ctx: typer.Context):
    config = init_config(ctx)
    user_token = ctx.params["user_token"]

    with session_manager(config.postgres_url) as session:
        user_id = get_user_id_if_exists(session, user_token)
        if not user_id:
            logging.info(f"No user found for token {user_token}, creating one")
            user_id = create_user_id(session, user_token)

        context = ElroyContext(session, StdIO(), config, user_id)
        set_system_persona(context, ctx.params["set_persona"])
    raise typer.Exit()


def handle_reset_persona(ctx: typer.Context):
    config = init_config(ctx)
    user_token = ctx.params["user_token"]

    with session_manager(config.postgres_url) as session:
        user_id = get_user_id_if_exists(session, user_token)
        if not user_id:
            logging.warning(f"No user found for token {user_token}, so no persona to clear")
            return typer.Exit()
        else:
            context = ElroyContext(session, StdIO(), config, user_id)
            reset_system_persona(context)
    raise typer.Exit()


def handle_show_persona(ctx: typer.Context):
    config = init_config(ctx)

    user_token = ctx.params["user_token"]

    with session_manager(config.postgres_url) as session:
        pipe(
            get_user_id_if_exists(session, user_token),
            partial(get_persona, session, config),
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


def validate_and_configure_db(postgres_url: Optional[str]):
    if not postgres_url:
        raise typer.BadParameter(
            "Postgres URL is required, please either set the ELROY_POSRTGRES_URL environment variable or run with --postgres-url"
        )
    if not _check_db_connectivity(postgres_url):
        raise typer.BadParameter("Could not connect to database. Please check if database is running and connection URL is correct.")

    _ensure_current_db_migration(postgres_url)


def _check_db_connectivity(postgres_url: str) -> bool:
    """Check if database is reachable by running a simple query"""
    try:
        with Session(create_engine(postgres_url)) as session:
            session.exec(text("SELECT 1")).first()  # type: ignore
            return True
    except Exception as e:
        logging.error(f"Database connectivity check failed: {e}")
        return False


def _ensure_current_db_migration(postgres_url: str) -> None:
    """Check if all migrations have been run.
    Returns True if migrations are up to date, False otherwise."""
    config = Config(os.path.join(ROOT_DIR, "alembic", "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_url)

    # Configure alembic logging to use Python's logging
    logging.getLogger("alembic").setLevel(logging.INFO)

    script = ScriptDirectory.from_config(config)
    engine = engine_from_config(
        config.get_section(config.config_ini_section),  # type: ignore
        prefix="sqlalchemy.",
    )

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_rev = context.get_current_revision()
        head_rev = script.get_current_head()

        if current_rev != head_rev:
            # Capture and redirect alembic output to logging

            with contextlib.redirect_stdout(StringIO()) as stdout:
                command.upgrade(config, "head")
                for line in stdout.getvalue().splitlines():
                    if line.strip():
                        logging.info(f"Alembic: {line.strip()}")
        else:
            logging.debug("Database is up to date.")
