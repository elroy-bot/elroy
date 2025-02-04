from elroy.api import Elroy
from elroy.config.ctx import ElroyContext


def test_message(ctx: ElroyContext):
    """Test the basic message functionality."""
    assistant = Elroy(token="testuser", database_url=ctx.db.url)
    response = assistant.message("This is a test: repeat the following words: Hello World")
    assert "hello world" in response.lower()


def test_get_persona(ctx: ElroyContext):
    """Test persona retrieval."""
    assistant = Elroy(token="testuser", database_url=ctx.db.url)
    persona = assistant.get_persona()
    assert isinstance(persona, str)
    assert len(persona) > 0
