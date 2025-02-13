import os

from tests import fixtures
from tests.utils import process_test_message

from elroy.config.ctx import ElroyContext
from elroy.repository.context_messages.operations import reset_messages
from elroy.repository.documents.tools import ingest_doc


def test_ingest_doc(ctx: ElroyContext):
    ingest_doc(ctx, os.path.join(os.path.dirname(fixtures.__file__), "the_midnight_garden.md"))
    reset_messages(ctx)

    response = process_test_message(ctx, "In the Midnight Garden, what was the name of the main character?")
    assert "clara" in response.lower()

    response = process_test_message(ctx, "What was the last sentence of the story, The Midnight Garden?")

    try:

        assert (
            """She knew that somewhere, perhaps even in her small town, there was another soul who would see the magic in her midnight garden and ensure its secrets would continue to flourish under the watchful eye of the moon."""
            in response
        )
    except AssertionError:
        print(response)
        raise
