from litellm.types.utils import Delta, ModelResponse, StreamingChoices

from elroy.config.ctx import ElroyContext
from elroy.llm.client import generate_chat_completion_message, query_llm
from elroy.repository.data_models import ContextMessage


def test_query_hello_world(ctx: ElroyContext):
    response = query_llm(
        model=ctx.chat_model,
        system="This is part of an automated test. Repeat the input text, specifically and without any extra text",
        prompt="Hello world",
    )

    assert "hello world" in response.lower()


def test_model_fallback(ctx: ElroyContext, mocker):
    from litellm.exceptions import RateLimitError

    # Mock completion to fail first time with rate limit error
    mock_completion = mocker.patch("litellm.completion")
    mock_completion.side_effect = [
        RateLimitError("Rate limit exceeded", "foo", "bar"),  # First call fails
        iter([ModelResponse(choices=[StreamingChoices(delta=Delta(content="hello world"))], finish_reason="stop")]),  # Second call succeeds
    ]

    messages = [
        ContextMessage(role="system", content="You are a test assistant", chat_model=ctx.chat_model.name),
        ContextMessage(role="user", content="Say hello", chat_model=ctx.chat_model.name),
    ]

    # This should trigger fallback from gpt-4 to gpt-3.5-turbo
    list(
        generate_chat_completion_message(
            ctx.chat_model,
            messages,
            tool_schemas=[],
        ).process()
    )

    # Verify completion was called twice - once with gpt-4, once with fallback
    assert mock_completion.call_count == 2

    # First call should use gpt-4
    assert mock_completion.call_args_list[0].kwargs["model"] != mock_completion.call_args_list[1].kwargs["model"]
