import uuid
from contextlib import contextmanager

from ..io.base import ElroyIO
from .ctx import ElroyContext
from .logging import get_logger
from .tracing import using_user

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
