from typing import Optional

from sqlmodel import Session, select
from toolz import pipe
from toolz.curried import do

from ..repository.data_models import User


def get_user_id_if_exist(session: Session, token: str) -> Optional[int]:
    user = session.exec(select(User).where(User.token == token)).first()

    if user:
        return user.id


def is_user_exists(session: Session, token: str) -> bool:
    return bool(session.exec(select(User).where(User.token == token)).first())


def create_user(session: Session, token: str) -> int:
    return pipe(
        User(token=token),
        do(session.add),
        do(lambda _: session.commit()),
        do(session.refresh),
        lambda user: user.id,
    )  # type: ignore
