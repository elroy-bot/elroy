from typing import Any, cast

from sqlmodel import Session, select

from ...db.db_models import User, UserPreference
from ...db.db_session import DbSession


class UserPreferenceStore:
    def __init__(self, db: DbSession, user_id: int):
        self.db = db
        self.user_id = user_id

    def get_or_create_user_preference(self) -> UserPreference:
        return do_get_or_create_user_preference(self.db.session, self.user_id)


def do_get_or_create_user_preference(session: Session, user_id: int) -> UserPreference:
    user_preference = session.exec(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            cast(Any, UserPreference.is_active),
        )
    ).first()

    if user_preference is None:
        user_preference = UserPreference(user_id=user_id, is_active=True)
        session.add(user_preference)
        session.commit()
        session.refresh(user_preference)
    return user_preference


def create_user_id(db: DbSession, user_token: str) -> int:
    user = db.persist(User(token=user_token))
    user_id = user.id
    assert user_id
    return user_id
