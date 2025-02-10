from functools import wraps
from typing import Callable, Generator, List, Optional

from .repository.recall.queries import get_sources

from .repository.recall.transforms import MemorySource

from .db.db_models import Memory

from .cli.options import get_resolved_params
from .config.constants import USER
from .config.ctx import ElroyContext
from .io.formatters.base import StringFormatter
from .io.formatters.plain_formatter import PlainFormatter
from .llm.stream_parser import AssistantInternalThought
from .messenger import process_message
from .repository.context_messages.data_models import ContextMessage
from .repository.context_messages.operations import add_context_messages
from .repository.context_messages.operations import (
    context_refresh as do_context_refresh,
)
from .repository.context_messages.queries import get_context_messages
from .repository.goals.operations import (
    add_goal_status_update as do_add_goal_status_update,
)
from .repository.goals.operations import create_goal as do_create_goal
from .repository.goals.operations import mark_goal_completed as do_mark_goal_completed
from .repository.goals.queries import get_active_goal_names as do_get_active_goal_names
from .repository.goals.queries import get_goal_by_name as do_get_goal_by_name
from .repository.memories.operations import create_memory as do_create_memory
from .repository.memories.queries import examine_memories as do_query_memory, get_active_memories
from .repository.user.operations import set_assistant_name, set_persona
from .repository.user.queries import get_persona as do_get_persona


def db(f: Callable) -> Callable:
    """Decorator to wrap non-generator function calls with database session context"""

    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if not self.ctx.is_db_connected():
            with self.ctx.dbsession():
                return f(self, *args, **kwargs)
        else:
            return f(self, *args, **kwargs)

    return wrapper


class Elroy:
    def __init__(
        self,
        *,
        token: Optional[str] = None,
        formatter: StringFormatter = PlainFormatter(),
        config_path: Optional[str] = None,
        persona: Optional[str] = None,
        assistant_name: Optional[str] = None,
        database_url: Optional[str] = None,
        **kwargs,
    ):
        self.formatter = formatter

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
        """Creates a goal. The goal can be for the AI user, or for the assistant in relation to helping the user somehow.
        Goals should be *specific* and *measurable*. They should be based on the user's needs and desires, and should
        be achievable within a reasonable timeframe.

        Args:
            goal_name (str): Name of the goal
            strategy (str): The strategy to achieve the goal. Your strategy should detail either how you (the personal assistant) will achieve the goal, or how you will assist your user to solve the goal. Limit to 100 words.
            description (str): A brief description of the goal. Limit to 100 words.
            end_condition (str): The condition that indicate to you (the personal assistant) that the goal is achieved or terminated. It is critical that this end condition be OBSERVABLE BY YOU (the assistant). For example, the end_condition may be that you've asked the user about the goal status.
            time_to_completion (str): The amount of time from now until the goal can be completed. Should be in the form of NUMBER TIME_UNIT, where TIME_UNIT is one of HOURS, DAYS, WEEKS, MONTHS. For example, "1 DAYS" would be a goal that should be completed within 1 day.
            priority (int, optional): The priority of the goal, from 0-4. Priority 0 is the highest priority, and 4 is the lowest.

        Returns:
            str: A confirmation message that the goal was created.

        Raises:
            ValueError: If goal_name is empty
            GoalAlreadyExistsError: If a goal with the same name already exists
        """
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
        """Captures either a progress update or note relevant to the goal.

        Args:
            goal_name (str): Name of the goal
            status_update_or_note (str): A brief status update or note about either progress or learnings relevant to the goal. Limit to 100 words.

        Returns:
            str: Confirmation message that the status update was added.
        """
        return do_add_goal_status_update(self.ctx, goal_name, status_update_or_note)

    @db
    def mark_goal_completed(self, goal_name: str, closing_comments: Optional[str] = None) -> str:
        """Marks a goal as completed, with closing comments.

        Args:
            goal_name (str): The name of the goal
            closing_comments (Optional[str]): Updated status with a short account of how the goal was completed and what was learned

        Returns:
            str: Confirmation message that the goal was marked as completed

        Raises:
            GoalDoesNotExistError: If the goal doesn't exist
        """
        return do_mark_goal_completed(self.ctx, goal_name, closing_comments)

    @db
    def get_active_goal_names(self) -> List[str]:
        """Gets the list of names for all active goals

        Returns:
            List[str]: List of names for all active goals
        """
        return do_get_active_goal_names(self.ctx)

    @db
    def get_memories(self) -> List[Memory]:
        """
        Returns a list of all active memories
        """

        memories = get_active_memories(self.ctx)
        self.ctx.db.session.expunge_all()
        return memories

    @db
    def get_memory_sources(self, memory: Memory) -> List[MemorySource]:
        """
        Returns the source of the memory
        """
        srcs = get_sources(self.ctx, memory)
        if srcs:
            self.ctx.db.session.expunge_all()
            return srcs
        else:
            return []


    @db
    def get_goal_by_name(self, goal_name: str) -> Optional[str]:
        """Get the fact for a goal by name

        Args:
            goal_name (str): Name of the goal

        Returns:
            Optional[str]: The fact for the goal with the given name
        """
        return do_get_goal_by_name(self.ctx, goal_name)

    @db
    def query_memory(self, query: str) -> str:
        """Search through memories and goals using semantic search.

        Args:
            query (str): The search query text to find relevant memories and goals

        Returns:
            str: A response synthesizing relevant memories and goals that match the query
        """
        return do_query_memory(self.ctx, query)

    @db
    def create_memory(self, name: str, text: str):
        """Creates a new memory for the assistant.

        Examples of good and bad memory titles are below. Note that in the BETTER examples, some titles have been split into two:

        BAD:
        - [User Name]'s project progress and personal goals: 'Personal goals' is too vague, and the title describes two different topics.

        BETTER:
        - [User Name]'s project on building a treehouse: More specific, and describes a single topic.
        - [User Name]'s goal to be more thoughtful in conversation: Describes a specific goal.

        BAD:
        - [User Name]'s weekend plans: 'Weekend plans' is too vague, and dates must be referenced in ISO 8601 format.

        BETTER:
        - [User Name]'s plan to attend a concert on 2022-02-11: More specific, and includes a specific date.

        BAD:
        - [User Name]'s preferred name and well being: Two different topics, and 'well being' is too vague.

        BETTER:
        - [User Name]'s preferred name: Describes a specific topic.
        - [User Name]'s feeling of rejuvenation after rest: Describes a specific topic.

        Args:
            name (str): The name of the memory. Should be specific and discuss one topic.
            text (str): The text of the memory.

        Returns:
            int: The database ID of the memory.
        """
        return do_create_memory(self.ctx, name, text)

    @db
    def message(self, input: str) -> str:
        """Process a message to the assistant and return the response

        Args:
            input (str): The message to process

        Returns:
            str: The response from the assistant
        """
        return "".join(list(self._message_stream(input)))

    def _message_stream(self, input: str) -> Generator[str, None, None]:
        """Process a message to the assistant and yield response chunks

        Args:
            input (str): The message to process

        Returns:
            Generator[str, None, None]: Generator yielding response chunks
        """
        for chunk in process_message(USER, self.ctx, input):
            if not isinstance(chunk, AssistantInternalThought) or self.ctx.show_internal_thought:
                yield from self.formatter.format(chunk)

    @db
    def context_refresh(self) -> None:
        """Compresses context messages and records a memory."""
        return do_context_refresh(self.ctx, get_context_messages(self.ctx))

    @db
    def get_persona(self) -> str:
        """Get the persona for the user, or the default persona if the user has not set one.

        Returns:
            str: The text of the persona.

        """
        return do_get_persona(self.ctx)

    @db
    def record_message(self, role: str, message: str) -> None:
        """Records a message into context, without generating a reply

        Args:
            role (str): The role of the message
            message (str): The message content
        """

        add_context_messages(
            self.ctx,
            ContextMessage(
                content=message,
                role=role,
                chat_model=None,
            ),
        )
