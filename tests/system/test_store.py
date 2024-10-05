import pytest

from elroy.store.data_models import User
from elroy.system.clock import get_utc_now


@pytest.fixture
def user():
    yield User(
        id=1,
        created_at=get_utc_now(),
        updated_at=get_utc_now(),
    )
