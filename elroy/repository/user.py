from typing import Optional

from sqlmodel import Session, select
from toolz import pipe
from toolz.curried import do

from ..repository.data_models import User


def get_or_create_user_id(session: Session, user_token: str) -> int:
    user_id = get_user_id_if_exists(session, user_token)

    if user_id is not None:
        return user_id
    else:
        return create_user_id(session, user_token)


def get_user_id_if_exists(session: Session, user_token: str) -> Optional[int]:
    user = session.exec(select(User).where(User.token == user_token)).first()
    return user.id if user else None


def is_user_exists(session: Session, user_token: str) -> bool:
    return bool(session.exec(select(User).where(User.token == user_token)).first())


def create_user_id(session: Session, user_token: str) -> int:
    return pipe(
        User(token=user_token),
        do(session.add),
        do(lambda _: session.commit()),
        do(session.refresh),
        lambda user: user.id,
    )  # type: ignore
