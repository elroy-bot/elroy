import pytest

from elroy.onboard_user import onboard_user
from elroy.store.user import get_user_id_by_phone
from elroy.tools.functions.user_preferences import get_user_preferred_name
from tests.fixtures import ALEX, SimulatedUser


def test_onboard_user_with_random_e164(session, phone_number):
    # Use the onboard_user function to create a new user
    new_user = onboard_user(session, phone_number)

    # Assert that the new user was created successfully
    assert new_user is not None

    user_id = get_user_id_by_phone(session, phone_number)

    assert user_id is not None


def test_onboard_user_with_invalid_phone(session):
    # Try to onboard a user with an invalid phone number
    with pytest.raises(ValueError, match="Invalid phone number format"):
        onboard_user(session, "12345")  # Not a valid E.164 format


def test_onboard_existing_user(session, phone_number):
    # Onboard a user
    onboard_user(session, phone_number)

    # Try to onboard another user with the same phone number
    with pytest.raises(ValueError, match="User with phone .* already exists"):
        onboard_user(session, phone_number)


def test_integration(session, user_id, phone_number):
    user = SimulatedUser(ALEX, user_id, phone_number)
    user.converse(session, 3)

    assert get_user_preferred_name(session, user.user_id) == ALEX.preferred_name

    # TODO: Check that goal is updated
