from elroy.core.ctx import ElroyContext
from elroy.llm.client import query_llm


def test_query_hello_world(ctx: ElroyContext):
    response = query_llm(
        model=ctx.chat_model,
        system="This is part of an automated test. Repeat the input text, specifically and without any extra text",
        prompt="Hello world",
    )

    assert "hello world" in response.lower()
