import logging
import uuid
from contextlib import contextmanager

from ..io.base import ElroyIO
from ..io.cli import CliIO
from .ctx import ElroyContext


@contextmanager
def init_elroy_session(ctx: ElroyContext, io: ElroyIO, check_db_migration: bool, should_onboard_interactive: bool):
    from ..cli.chat import onboard_interactive, onboard_non_interactive
    from ..repository.user.queries import get_user_id_if_exists
    from ..tools.inline_tools import verify_inline_tool_call_instruct_matches_ctx

    try:
        if check_db_migration:
            ctx.db_manager.check_connection()
            ctx.db_manager.migrate_if_needed()

        session_id = str(uuid.uuid4())
        logging.info(f"OpenTelemetry instrumentation enabled with session ID: {session_id}")
        from openinference.instrumentation import using_session

        with using_session(session_id=session_id):
            import litellm

            litellm.callbacks = ["otel"]  # noqa F841

            with ctx.db_manager.open_session() as dbsession:
                ctx.set_db_session(dbsession)

                if not get_user_id_if_exists(dbsession, ctx.user_token):
                    if should_onboard_interactive and isinstance(io, CliIO):
                        onboard_interactive(io, ctx)
                    else:
                        onboard_non_interactive(ctx)

                verify_inline_tool_call_instruct_matches_ctx(ctx)

                yield

    finally:
        ctx.unset_db_session()


@contextmanager
def dbsession(ctx: ElroyContext):
    if ctx.is_db_connected():
        yield
    else:
        with ctx.db_manager.open_session() as dbsession:
            try:
                ctx.set_db_session(dbsession)
                yield
            finally:
                ctx.unset_db_session()
