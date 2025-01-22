from datetime import datetime
from functools import wraps
from typing import Callable, Generator, Optional

from pytz import UTC

from .cli.options import get_resolved_params
from .config.constants import USER
from .config.ctx import ElroyContext
from .llm.persona import get_persona as do_get_persona
from .llm.stream_parser import AssistantInternalThought
from .messaging.messenger import process_message
from .repository.memories.operations import create_memory
from .tools.user_preferences import set_assistant_name, set_persona


def db(f: Callable) -> Callable:
    """Decorator to wrap function calls with database session context"""

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if not self.ctx.is_db_connected():
            with self.ctx.dbsession():
                return f(self, *args, **kwargs)

    return wrapper


class Elroy:
    ctx: ElroyContext

    def __init__(
        self,
        token: Optional[str] = None,
        config_path: Optional[str] = None,
        persona: Optional[str] = None,
        assistant_name: Optional[str] = None,
        database_url: Optional[str] = None,
    ):

        self.ctx = ElroyContext(
            **get_resolved_params(
                user_token=token,
                config_path=config_path,
                database_url=database_url,
            ),
        )
        with self.ctx.dbsession():
            if persona:
                set_persona(self.ctx, persona)

            if assistant_name:
                set_assistant_name(self.ctx, assistant_name)

    @db
    def message(self, input: str) -> str:
        return "".join(self.message_stream(input))

    def message_stream(self, input: str) -> Generator[str, None, None]:
        stream = [
            chunk.content
            for chunk in process_message(USER, self.ctx, input)
            if not isinstance(chunk, AssistantInternalThought) or self.ctx.show_internal_thought
        ]
        if not self.ctx.is_db_connected():
            with self.ctx.dbsession():
                yield from stream
        else:
            yield from stream

    @db
    def remember(self, message: str, name: Optional[str] = None) -> None:
        if not name:
            name = f"Memory from {datetime.now(UTC)}"
        create_memory(self.ctx, name, message)

    @db
    def get_persona(self) -> str:
        return do_get_persona(self.ctx)
