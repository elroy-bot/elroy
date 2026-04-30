from elroy.core.ctx import ElroyConfig
from elroy.core.session import invoke_with_config, open_turn_context
from elroy.repository.context_messages.tools import reset_messages
from elroy.repository.user.queries import do_get_user_preferred_name
from elroy.repository.user.session import build_user_session
from elroy.repository.user.tools import (
    reset_system_persona,
    set_assistant_name,
    set_persona,
)
from tests.utils import process_test_message


def test_update_user_preferred_name(ctx: ElroyConfig):

    process_test_message(
        ctx,
        "Please call me TestUser500 from now on.",
    )

    with open_turn_context(ctx) as turn:
        user_session = build_user_session(turn)
    assert do_get_user_preferred_name(user_session.db.session, user_session.user_id) == "TestUser500"


def test_update_persona(ctx):
    reply = process_test_message(ctx, "What is your name?")

    assert "elroy" in reply.lower()

    invoke_with_config(
        set_persona,
        ctx,
        system_persona="You are a helpful assistant.Your name is JarvisIf asked what your name is, be sure to reply with Jarvis",
    )

    reply = process_test_message(ctx, "What is your name?")

    assert "jarvis" in reply.lower()
    assert "elroy" not in reply.lower()

    reply = process_test_message(ctx, "What is your name?")

    invoke_with_config(reset_system_persona, ctx)


def test_assistant_name(ctx):
    assert "elroy" in process_test_message(ctx, "What is your name?").lower()

    invoke_with_config(set_assistant_name, ctx, assistant_name="Jimbo")
    invoke_with_config(reset_messages, ctx)

    assert "jimbo" in process_test_message(ctx, "What is your name?").lower()
