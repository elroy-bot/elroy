import pytest
from tests.utils import process_test_message

from elroy.core.constants import InvalidForceToolError
from elroy.repository.user.queries import do_get_user_preferred_name
from elroy.repository.user.tools import set_user_preferred_name


@pytest.mark.flaky(reruns=3)
def test_hello_world(ctx):
    # Test message
    test_message = "Hello, World!"

    # Get the argument passed to the delivery function
    response = process_test_message(ctx, test_message)

    # Assert that the response is a non-empty string
    assert isinstance(response, str)
    assert len(response) > 0

    # Assert that the response contains a greeting
    assert any(greeting in response.lower() for greeting in ["hello", "hi", "greetings"])


def test_force_tool(ctx):
    process_test_message(ctx, "Jimmy", set_user_preferred_name.__name__)
    assert ctx.user_preferred_name == "Jimmy"
    assert do_get_user_preferred_name(ctx.db.session, ctx.user_id) == "Jimmy"


def test_force_invalid_tool(ctx):
    with pytest.raises(InvalidForceToolError):
        process_test_message(ctx, "Jimmy", "invalid_tool")
