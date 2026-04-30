from elroy.core.ctx import ElroyConfig


def test_query_hello_world(ctx: ElroyConfig):
    response = ctx.llm.query_llm(
        system="This is part of an automated test. Repeat the input text, specifically and without any extra text",
        prompt="Hello world",
    )

    assert "hello world" in response.lower()
