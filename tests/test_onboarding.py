from elroy.tools.functions.user_preferences import get_user_preferred_name
from tests.fixtures import ALEX, SimulatedUser


def test_integration(session, user_id):
    user = SimulatedUser(ALEX, user_id)
    user.converse(session, 3)

    assert get_user_preferred_name(session, user.user_id) == ALEX.preferred_name

    # TODO: Check that goal is updated
