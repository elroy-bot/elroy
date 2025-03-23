import uuid
from unittest.mock import patch

import pytest
from litellm.exceptions import ContentPolicyViolationError

from elroy.core.constants import USER
from elroy.core.ctx import ElroyContext
from elroy.llm.stream_parser import AssistantResponse
from elroy.messenger.messenger import process_message


@pytest.skip("Need to implement mockable client")
def test_content_violation_recovery(ctx: ElroyContext):
    """Test that content violation triggers context refresh and retries"""

    error = ContentPolicyViolationError(
        message=str(
            {
                "error": {
                    "message": "Content policy violation",
                    "innererror": {"content_filter_result": {"jailbreak": {"filtered": True, "detected": True}}},
                }
            }
        ),
        model="test-model",
        llm_provider="azure",
    )

    # Mock first call fails, then use real function
    with patch(
        "elroy.messenger.messenger.generate_chat_completion_message",
        side_effect=[error, lambda *args, **kwargs: iter([AssistantResponse("ok response")])],
    ) as mock_gen:
        results = list(process_message(USER, ctx, "test message"))

        assert len(results) == 1
        assert isinstance(results[0], AssistantResponse)
        assert results[0].content == "ok response"

        # Should have tried twice
        assert mock_gen.call_count == 2


@pytest.skip("Need to implement mockable client")
def test_content_violation_multiple_retries(ctx: ElroyContext, content_policy_violation_error: ContentPolicyViolationError):
    """Test handling multiple content violations"""

    # First two fail, third succeeds
    responses = [content_policy_violation_error, content_policy_violation_error, iter([AssistantResponse("final ok response")])]

    with patch("elroy.messenger.messenger.generate_chat_completion_message") as mock_gen:
        mock_gen.side_effect = responses  # noqa F841

        results = list(process_message(USER, ctx, "test message"))

        assert len(results) == 1
        assert isinstance(results[0], AssistantResponse)
        assert results[0].content == "final ok response"

        # Should have tried three times
        assert mock_gen.call_count == 3


@pytest.skip("Need to implement mockable client")
def test_content_violation_final_failure(ctx: ElroyContext, content_policy_violation_error: ContentPolicyViolationError):
    """Test handling when all retries fail"""

    # All attempts fail
    responses = [
        content_policy_violation_error,
        content_policy_violation_error,
        content_policy_violation_error,
    ]

    with patch("elroy.messenger.messenger.generate_chat_completion_message") as mock_gen:
        mock_gen.side_effect = responses  # noqa F841

        results = list(process_message(USER, ctx, "test message"))

        assert len(results) == 1
        assert isinstance(results[0], AssistantResponse)
        assert "violated the LLM provider's content policy" in results[0].content

        # Should have tried three times
        assert mock_gen.call_count == 3


@pytest.fixture(scope="function")
def content_policy_violation_error(ctx: ElroyContext) -> ContentPolicyViolationError:
    return ContentPolicyViolationError(message=uuid.uuid4().hex, model="unknown", llm_provider="unknown")
