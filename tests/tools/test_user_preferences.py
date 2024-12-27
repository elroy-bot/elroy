from tests.utils import process_test_message

from elroy.tools.user_preferences import (
    get_user_preferred_name,
    reset_system_persona,
    set_assistant_name,
    set_system_persona,
)


def test_update_user_preferred_name(elroy_context):

    process_test_message(
        elroy_context,
        "Please call me TestUser500 from now on.",
    )

    assert get_user_preferred_name(elroy_context) == "TestUser500"


def test_update_persona(elroy_context):
    reply = process_test_message(elroy_context, "What is your name?")

    assert "elroy" in reply.lower()

    set_system_persona(
        elroy_context, "You are a helpful assistant." "Your name is Jarvis" "If asked what your name is, be sure to reply with Jarvis"
    )

    reply = process_test_message(elroy_context, "What is your name?")

    assert "jarvis" in reply.lower()
    assert "elroy" not in reply.lower()

    reply = process_test_message(elroy_context, "What is your name?")

    reset_system_persona(elroy_context)


def test_assistant_name(elroy_context):
    reply = process_test_message(elroy_context, "What is your name?")

    assert "elroy" in reply.lower()

    set_assistant_name(elroy_context, "Jimbo")

    reply = process_test_message(elroy_context, "What is your name?")

    assert "jimbo" in reply.lower()
