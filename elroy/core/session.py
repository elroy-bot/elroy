from contextlib import contextmanager

from .ctx import ElroyContext
from .logging import get_logger

logger = get_logger()


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
