from elroy.core.ctx import ElroyContext
from elroy.llm.client import query_llm


def test_query_hello_world(ctx: ElroyContext):
    # Test using the new client interface
    response = ctx.llm_client.query_llm(
        model=ctx.chat_model,
        system="This is part of an automated test. Repeat the input text, specifically and without any extra text",
        prompt="Hello world",
    )

    assert "hello world" in response.lower()


def test_query_hello_world_legacy(ctx: ElroyContext):
    # Test that the legacy function interface still works
    response = query_llm(
        model=ctx.chat_model,
        system="This is part of an automated test. Repeat the input text, specifically and without any extra text",
        prompt="Hello world",
    )

    assert "hello world" in response.lower()
