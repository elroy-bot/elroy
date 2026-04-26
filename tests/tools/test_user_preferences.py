from elroy.core.ctx import ElroyContext
from elroy.core.db import require_db_session
from elroy.repository.context_messages.tools import reset_messages
from elroy.repository.user.queries import do_get_user_preferred_name
from elroy.repository.user.tools import (
    reset_system_persona,
    set_assistant_name,
    set_persona,
)
from tests.utils import process_test_message


def test_update_user_preferred_name(ctx: ElroyContext):

    process_test_message(
        ctx,
        "Please call me TestUser500 from now on.",
    )

    assert do_get_user_preferred_name(require_db_session(ctx).session, ctx.user_id) == "TestUser500"


def test_update_persona(ctx):
    reply = process_test_message(ctx, "What is your name?")

    assert "elroy" in reply.lower()

    set_persona(ctx, "You are a helpful assistant.Your name is JarvisIf asked what your name is, be sure to reply with Jarvis")

    reply = process_test_message(ctx, "What is your name?")

    assert "jarvis" in reply.lower()
    assert "elroy" not in reply.lower()

    reply = process_test_message(ctx, "What is your name?")

    reset_system_persona(ctx)


def test_assistant_name(ctx):
    assert "elroy" in process_test_message(ctx, "What is your name?").lower()

    set_assistant_name(ctx, "Jimbo")
    reset_messages(ctx)

    assert "jimbo" in process_test_message(ctx, "What is your name?").lower()
