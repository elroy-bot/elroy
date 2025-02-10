from tests.utils import process_test_message

from elroy.config.ctx import ElroyContext
from elroy.repository.documents.chunker import scrape_doc

# Ideal ux: some kind of progress bar indicating ingestion progress in CLI


def test_markdown(ctx: ElroyContext):
    for x in [
        "https://github.com/pebble-dev/mobile-app/blob/master/README.md",
        "https://github.com/elroy-bot/elroy/blob/main/README.md",
    ]:
        scrape_doc(ctx, x)

    response = process_test_message(
        ctx, "What do I need to put in my Create `local.properties` file in `android` folder. when developing for rebble app?"
    )
    assert "GITHUB_ACTOR" in response.upper()
