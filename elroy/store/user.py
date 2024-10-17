from sqlmodel import Session, select
from toolz import pipe
from toolz.curried import do

from elroy.config import ElroyContext
from elroy.store.data_models import User, UserPreference


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


assistant_writable_user_preference_fields = set(UserPreference.model_fields.keys()) - {
    "id",
    "created_at",
    "updated_at",
    "user_id",
    "is_active",
}
