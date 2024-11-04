import pytest

from elroy.repository.data_models import User
from elroy.utils.clock import get_utc_now


@pytest.fixture
def user():
    yield User(
        id=1,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
