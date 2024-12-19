from typing import Optional, Tuple

from sqlmodel import Session, select
from toolz import pipe
from toolz.curried import do

from ..db.db_manager import DbManager
from ..db.db_models import User


def get_or_create_user_id(db: DbManager, user_token: str) -> Tuple[int, bool]:
    """
    Returns:
    int: user id for token
    bool: True if a new user was created, false if not.
    """
    user_id = get_user_id_if_exists(db, user_token)

    if user_id is not None:
        return (user_id, False)
    else:
        return (create_user_id(db, user_token), True)


def get_user_id_if_exists(db: DbManager, user_token: str) -> Optional[int]:
    user = db.exec(select(User).where(User.token == user_token)).first()
    return user.id if user else None


def is_user_exists(session: Session, user_token: str) -> bool:
    return bool(session.exec(select(User).where(User.token == user_token)).first())


def create_user_id(db: DbManager, user_token: str) -> int:
    return pipe(
        User(token=user_token),
        do(db.add),
        do(lambda _: db.commit()),
        do(db.refresh),
        lambda user: user.id,
    )  # type: ignore
