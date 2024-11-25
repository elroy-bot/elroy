from elroy.config.config import ElroyContext
from elroy.llm.client import query_llm


def test_query_hello_world(elroy_context: ElroyContext):
    response = query_llm(
        model=elroy_context.config.chat_model,
        system="This is part of an automated test. Repeat the input text, specifically and without any extra text",
        prompt="Hello world",
    )

    assert "hello world" in response.lower()
