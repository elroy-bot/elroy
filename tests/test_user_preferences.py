
import pytest

from elroy.tools.functions.user_preferences import get_user_preferred_name
from elroy.tools.messenger import process_message


def test_update_user_preferred_name(session, onboarded_user_id):

    process_message(
        session,
        onboarded_user_id,
        "Please call me TestUser500 from now on.",
    )

    assert get_user_preferred_name(session, onboarded_user_id) == "TestUser500"


@pytest.mark.skip(reason="TODO")
def test_update_user_time_zone():
    pass
