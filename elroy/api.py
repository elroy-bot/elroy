from datetime import datetime
from functools import wraps
from typing import Callable, Generator, List, Optional

from pytz import UTC

from .cli.options import get_resolved_params
from .config.constants import USER
from .config.ctx import ElroyContext
from .llm.persona import get_persona as do_get_persona
from .llm.stream_parser import AssistantInternalThought
from .messaging.messenger import process_message
from .repository.goals.operations import (
    add_goal_status_update as do_add_goal_status_update,
)
from .repository.goals.operations import create_goal as do_create_goal
from .repository.goals.operations import mark_goal_completed as do_mark_goal_completed
from .repository.memories.operations import create_memory
from .repository.memories.operations import create_memory as do_create_memory
from .system_commands import get_active_goal_names as do_get_active_goal_names
from .system_commands import get_goal_by_name as do_get_goal_by_name
from .system_commands import query_memory as do_query_memory
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
    def __init__(
        self,
        *,
        token: Optional[str] = None,
        config_path: Optional[str] = None,
        persona: Optional[str] = None,
        assistant_name: Optional[str] = None,
        database_url: Optional[str] = None,
        **kwargs,
    ):

        self.ctx = ElroyContext(
            **get_resolved_params(
                user_token=token,
                config_path=config_path,
                database_url=database_url,
                **kwargs,
            ),
        )
        with self.ctx.dbsession():
            if persona:
                set_persona(self.ctx, persona)

            if assistant_name:
                set_assistant_name(self.ctx, assistant_name)

    @db
    def create_goal(
        self,
        goal_name: str,
        strategy: Optional[str] = None,
        description: Optional[str] = None,
        end_condition: Optional[str] = None,
        time_to_completion: Optional[str] = None,
        priority: Optional[int] = None,
    ) -> str:
        return do_create_goal(
            self.ctx,
            goal_name,
            strategy,
            description,
            end_condition,
            time_to_completion,
            priority,
        )

    @db
    def add_goal_status_update(self, goal_name: str, status_update_or_note: str) -> str:
        return do_add_goal_status_update(self.ctx, goal_name, status_update_or_note)

    @db
    def mark_goal_completed(self, goal_name: str, closing_comments: Optional[str] = None) -> str:
        return do_mark_goal_completed(self.ctx, goal_name, closing_comments)

    @db
    def get_active_goal_names(self) -> List[str]:
        return do_get_active_goal_names(self.ctx)

    @db
    def get_goal_by_name(self, goal_name: str) -> Optional[str]:
        return do_get_goal_by_name(self.ctx, goal_name)

    @db
    def query_memory(self, query: str) -> str:
        return do_query_memory(self.ctx, query)

    @db
    def create_memory(self, name: str, text: str):
        return do_create_memory(self.ctx, name, text)

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
