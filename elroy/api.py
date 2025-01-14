from datetime import datetime
from typing import Generator, Optional

from pytz import UTC

from .cli.options import get_resolved_params
from .config.constants import USER
from .config.ctx import ElroyContext
from .llm.stream_parser import AssistantInternalThought
from .messaging.messenger import process_message
from .repository.memories.operations import create_memory


class Elroy:
    ctx: ElroyContext

    def __init__(
        self,
        user_token: Optional[str] = None,
        config_path: Optional[str] = None,
    ):
        self.ctx = ElroyContext(
            **get_resolved_params(
                user_token=user_token,
                config_path=config_path,
            ),
        )

    def message(self, input: str) -> str:
        return "".join(self.message_stream(input))

    def message_stream(self, input: str) -> Generator[str, None, None]:
        with self.ctx.dbsession():
            for chunk in process_message(USER, self.ctx, input):
                if not isinstance(chunk, AssistantInternalThought) or self.ctx.show_internal_thought:
                    yield chunk.content

    def remember(self, message: str, name: Optional[str] = None) -> None:
        with self.ctx.dbsession():
            if not name:
                name = f"Memory from {datetime.now(UTC)}"
            create_memory(self.ctx, name, message)
