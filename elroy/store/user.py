from datetime import datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Session, SQLModel, select
from toolz import pipe
from toolz.curried import do

from elroy.config import ElroyContext
from elroy.store.data_models import User
from elroy.system.clock import get_utc_now


def is_user_exists(context: ElroyContext) -> bool:
    return bool(context.session.exec(select(User).where(User.id == context.user_id)).first())


def create_user(session: Session) -> int:
    return pipe(
        User(),
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
