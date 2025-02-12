from contextlib import contextmanager

from ..config.ctx import ElroyContext
from ..io.base import ElroyIO
from ..io.cli import CliIO


@contextmanager
def get_db_session(ctx: ElroyContext, io: ElroyIO):
    if ctx.is_migration_needed():
        if isinstance(io, CliIO):
            with io.status("Updating database..."):
                ctx.migrate_db()
        else:
            ctx.migrate_db()

    with ctx.dbsession():
        yield
