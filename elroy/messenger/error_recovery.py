from functools import wraps
from time import sleep
from typing import Iterator, Optional, Union

from httpx import RemoteProtocolError

from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..db.db_models import FunctionCall
from ..llm.stream_parser import (
    AssistantInternalThought,
    AssistantResponse,
    AssistantToolResult,
    CodeBlock,
)

logger = get_logger()


def handle_remote_protocol_error(func):
    @wraps(func)
    def wrapper(
        role: str,
        ctx: ElroyContext,
        msg: str,
        enable_tools: bool = True,
        force_tool: Optional[str] = None,
    ) -> Iterator[Union[AssistantResponse, AssistantInternalThought, CodeBlock, AssistantToolResult, FunctionCall]]:
        from litellm.exceptions import APIConnectionError, APIError

        attempt = 0
        while True:
            try:
                yield from func(role, ctx, msg, enable_tools, force_tool)
                break
            except (RemoteProtocolError, APIConnectionError, APIError) as e:
                if attempt >= 5:
                    raise
                logger.warning(f"Remote protocol error: {str(e)}")
                attempt += 1
                sleep_duration_secs = 2**attempt
                logger.warning(f"Retrying in {sleep_duration_secs} seconds")
                sleep(sleep_duration_secs)
            except Exception as e:
                logger.error(f"Unexpected error of type: {type(e)}")
                raise

    return wrapper
