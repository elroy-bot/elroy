from typing import Optional

from sqlmodel import Session, select
from toolz import pipe
from toolz.curried import do

from ..db.db_manager import DbManager
from ..db.db_models import User


def get_user_id_if_exists(db: DbManager, user_token: str) -> Optional[int]:
    user = db.exec(select(User).where(User.token == user_token)).first()
    if user:
        id = user.id
        assert id
        return id


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
