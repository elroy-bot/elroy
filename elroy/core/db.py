from ..db.db_session import DbSession
from .ctx import ElroyContext


def require_db_session(ctx: ElroyContext) -> DbSession:
    db_session = ctx._db
    if db_session is None:
        raise ValueError("No db session open")
    return db_session
