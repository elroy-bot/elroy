from datetime import datetime
from functools import partial
from typing import Any, List, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Session, SQLModel, select
from toolz import pipe
from toolz.curried import do

from elroy.store.data_models import User
from elroy.system.clock import get_utc_now


def get_user_by_field(field_name: str, session: Session, value: Any) -> User:
    user = session.exec(select(User).where(getattr(User, field_name) == value)).first()
    if not user:
        raise KeyError(f"User with {field_name} {value} not found")
    return user


def get_user_id_by_field(field_name: str, session: Session, value: Any) -> int:
    id = get_user_by_field(field_name, session, value).id
    assert id
    return id


def get_admins(session: Session) -> List[User]:
    return session.exec(select(User).where(User.is_admin == True)).all()  # type: ignore


def get_all_user_ids(session: Session) -> List[int]:
    return [user.id for user in session.exec(select(User)).all() if user.id is not None]


get_user_id_by_email = partial(get_user_id_by_field, "email")
get_user_id_by_phone = partial(get_user_id_by_field, "phone")


def get_user_phone_by_id(session: Session, user_id: int) -> str:
    return get_user_by_field("id", session, user_id).phone


def is_user_exists(session: Session, user_id: int) -> bool:
    return bool(session.exec(select(User).where(User.id == user_id)).first())


def is_user_premium(session: Session, user_id: int) -> bool:
    return get_user_by_field("id", session, user_id).is_premium


def create_user(session: Session, phone: str) -> int:
    return pipe(
        User(phone=phone),
        do(session.add),
        do(lambda _: session.commit()),
        do(session.refresh),
        lambda user: user.id,
    )  # type: ignore


class UserPreference(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "is_active"), {"extend_existing": True})
    id: Optional[int] = Field(default=None, description="The unique identifier for the user", primary_key=True, index=True)
    created_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=get_utc_now, nullable=False)
    user_id: int = Field(..., description="User for context")
    preferred_name: Optional[str] = Field(default=None, description="The preferred name for the user")
    full_name: Optional[str] = Field(default=None, description="The full name for the user")
    user_time_zone: Optional[str] = Field(default=None, description="The time zone for the user")
    display_internal_monologue: Optional[bool] = Field(default=False, description="Whether the internal monologue should be displayed")
    is_active: Optional[bool] = Field(default=True, description="Whether the context is active")


assistant_writable_user_preference_fields = set(UserPreference.model_fields.keys()) - {
    "id",
    "created_at",
    "updated_at",
    "user_id",
    "is_active",
}
