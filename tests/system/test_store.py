import pytest
from pydantic import ValidationError

from elroy.store.data_models import User
from elroy.system.clock import get_utc_now


@pytest.fixture
def user():
    yield User(
        id=1,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
        phone="+12345678901",
        email="foobar@gmail.com",
        is_premium=False,
        is_admin=False,
    )


def test_phone_happy(user: User):
    # Test a valid E.164 number
    good_phone = "+12345678901"
    user.phone = good_phone
    User.model_validate(user)


def test_phone_sad(user: User):
    bad_phone = "12345678901"
    user.phone = bad_phone
    with pytest.raises(ValidationError):
        user = User(phone=bad_phone)
        User.model_validate(user)
