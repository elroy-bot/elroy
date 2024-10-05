from functools import partial

import pytest

from elroy.system.parameters import INNER_THOUGHT_TAG
from elroy.tools.functions.user_preferences import (
    get_display_internal_monologue, get_user_preferred_name)
from elroy.tools.messenger import process_message


def test_update_user_preferred_name(session, onboarded_user_id):

    process_message(
        session,
        onboarded_user_id,
        "Please call me TestUser500 from now on.",
    )

    assert get_user_preferred_name(session, onboarded_user_id) == "TestUser500"


def test_internal_monologue(session, onboarded_user_id):
    assert get_display_internal_monologue(session, onboarded_user_id) is False

    process_test_message = partial(
        process_message,
        session,
        onboarded_user_id,
    )

    assert INNER_THOUGHT_TAG not in process_test_message("hello")

    process_test_message("Please turn on internal thought monologue")

    assert get_display_internal_monologue(session, onboarded_user_id) is True

    assert INNER_THOUGHT_TAG in process_test_message("What is 2 + 2?")


@pytest.mark.skip(reason="TODO")
def test_update_user_time_zone():
    pass


@pytest.mark.skip(reason="TODO")
def test_update_user_preferred_checkin_cadence():
    pass
