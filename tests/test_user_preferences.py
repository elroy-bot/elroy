from elroy.tools.functions.user_preferences import get_user_preferred_name
from tests.utils import process_test_message


def test_update_user_preferred_name(onboarded_context):

    process_test_message(
        onboarded_context,
        "Please call me TestUser500 from now on.",
    )

    assert get_user_preferred_name(onboarded_context) == "TestUser500"
