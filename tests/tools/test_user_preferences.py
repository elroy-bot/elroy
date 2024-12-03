from tests.utils import process_test_message

from elroy.tools.user_preferences import get_user_preferred_name


def test_update_user_preferred_name(elroy_context):

    process_test_message(
        elroy_context,
        "Please call me TestUser500 from now on.",
    )

    assert get_user_preferred_name(elroy_context) == "TestUser500"
