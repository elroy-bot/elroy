from functools import wraps
from time import sleep
from typing import Iterator, Optional, Union

from httpx import RemoteProtocolError
from litellm.exceptions import ContentPolicyViolationError

from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..db.db_models import FunctionCall
from ..llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    AssistantToolResult,
    CodeBlock,
)
from ..repository.context_messages.operations import context_refresh, reset_messages
from ..repository.context_messages.queries import get_context_messages

logger = get_logger()


def handle_content_violation(func):
    @wraps(func)
    def wrapper(
        role: str,
        ctx: ElroyContext,
        msg: str,
        enable_tools: bool = True,
        force_tool: Optional[str] = None,
    ) -> Iterator[Union[AssistantResponse, AssistantInternalThought, CodeBlock, AssistantToolResult, FunctionCall]]:
        try:
            yield from func(role, ctx, msg, enable_tools, force_tool)
            return
        except ContentPolicyViolationError as e:
            logger.warning(str(e))

        logger.info("Attempting to recover from content filter violation: refreshing context")
        context_refresh(ctx, get_context_messages(ctx))

        try:
            yield from func(role, ctx, msg, enable_tools, force_tool)
            return
        except ContentPolicyViolationError as e:
            logger.warning(str(e))

        logger.warning("Content filter warning detected again, resetting context messages")
        reset_messages(ctx)

        try:
            yield from func(role, ctx, msg, enable_tools, force_tool)
            return
        except ContentPolicyViolationError as e:
            logger.warning(str(e))
            logger.warning("Content filter warning again, aborting message processing")

        yield AssistantResponse("Your message violated the LLM provider's content policy. Please try again with a different message.")

    return wrapper


def handle_remote_protocol_error(func):
    @wraps(func)
    def wrapper(
        role: str,
        ctx: ElroyContext,
        msg: str,
        enable_tools: bool = True,
        force_tool: Optional[str] = None,
    ) -> Iterator[Union[AssistantResponse, AssistantInternalThought, CodeBlock, AssistantToolResult, FunctionCall]]:

        attempt = 0
        while True:
            try:
                yield from func(role, ctx, msg, enable_tools, force_tool)
                break
            except RemoteProtocolError as e:
                if attempt >= 3:
                    raise
                logger.warning(f"Remote protocol error: {str(e)}")
                attempt += 1
                sleep_duration_secs = 2**attempt
                logger.warning(f"Retrying in {sleep_duration_secs} seconds")
                sleep(sleep_duration_secs)

    return wrapper
