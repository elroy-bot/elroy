import logging
from collections import deque
from datetime import datetime, timedelta
from functools import partial, reduce
from operator import add
from typing import List, Optional

from sqlmodel import select
from tiktoken import encoding_for_model
from toolz import concat, pipe
from toolz.curried import filter, map, remove

from ..config.config import ElroyContext
from ..config.constants import CHAT_MODEL
from ..llm.persona import persona
from ..llm.prompts import summarize_conversation
from ..repository.data_models import (
    ASSISTANT,
    TOOL,
    USER,
    ContextMessage,
    EmbeddableSqlModel,
    Goal,
    Memory,
)
from ..repository.embeddings import find_redundant_pairs
from ..repository.facts import to_fact
from ..repository.memory import consolidate_memories
from ..repository.message import (
    ContextMessage,
    MemoryMetadata,
    add_context_messages,
    get_context_messages,
    get_time_since_context_message_creation,
    remove_context_messages,
    replace_context_messages,
)
from ..utils.clock import get_utc_now
from ..utils.utils import datetime_to_string, logged_exec_time


def get_refreshed_system_message(user_preferred_name: str, context_messages: List[ContextMessage]) -> ContextMessage:
    assert isinstance(context_messages, list)
    if len(context_messages) > 0 and context_messages[0].role == "system":
        # skip existing system message if it is still in context.
        context_messages = context_messages[1:]

    if len([msg for msg in context_messages if msg.role == USER]) == 0:
        conversation_summary = None
    else:
        conversation_summary = pipe(
            context_messages,
            lambda msgs: format_context_messages(user_preferred_name, msgs),
            summarize_conversation,
            lambda _: f"<conversational_summary>{_}</conversational_summary>",
            str,
        )

    return pipe(
        [
            f"<persona>{persona(user_preferred_name)}</persona>",
            conversation_summary,
            "From now on, converse as your persona.",
        ],  # type: ignore
        remove(lambda _: _ is None),
        "".join,
        lambda x: ContextMessage(role="system", content=x),
    )


def format_message(user_preferred_name: str, message: ContextMessage) -> Optional[str]:
    datetime_str = datetime_to_string(message.created_at)
    if message.role == "system":
        return f"SYSTEM ({datetime_str}): {message.content}"
    elif message.role == USER:
        return f"{user_preferred_name.upper()} ({datetime_str}): {message.content}"
    elif message.role == ASSISTANT:
        if message.content:
            return f"ELROY ({datetime_str}): {message.content}"
        elif message.tool_calls:
            return f"ELROY TOOL CALL ({datetime_str}): {message.tool_calls[0].function['name']}"
        else:
            raise ValueError(f"Expected either message text or tool call: {message}")


# passing message content is an approximation, tool calls may not be accounted for.
def count_tokens(s: Optional[str]) -> int:
    if not s or s == "":
        return 0
    else:
        encoding = encoding_for_model(CHAT_MODEL)
        return len(encoding.encode(s))


def is_context_refresh_needed(context: ElroyContext) -> bool:
    context_messages = get_context_messages(context)

    if sum(1 for m in context_messages if m.role == USER) == 0:
        logging.info("No user messages in context, skipping context refresh")
        return False

    token_count = pipe(
        context_messages,
        map(lambda _: _.content),
        remove(lambda _: _ is None),
        map(count_tokens),
        lambda seq: reduce(add, seq, 0),
    )
    assert isinstance(token_count, int)

    if token_count > context.config.context_refresh_token_trigger_limit:
        logging.info(f"Token count {token_count} exceeds threshold {context.config.context_refresh_token_trigger_limit}")
        return True
    else:
        logging.info(f"Token count {token_count} does not exceed threshold {context.config.context_refresh_token_trigger_limit}")

    elapsed_time = get_time_since_context_message_creation(context)
    threshold = timedelta(seconds=context.config.context_refresh_interval_seconds)
    if not elapsed_time or elapsed_time > threshold:
        logging.info(f"Context watermark age {elapsed_time} exceeds threshold {threshold}")
        return True
    else:
        logging.info(f"Context watermark age {elapsed_time} is below threshold {threshold}")

    return False


def compress_context_messages(context: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    """Refreshes context, saving to archival memory and compressing the context window."""

    system_message, prev_messages = context_messages[0], context_messages[1:]

    new_messages = deque()
    current_token_count = count_tokens(system_message.content)
    most_recent_kept_message = None  # we will keep track of what message we last decided to keep

    # iterate through non-system context messages in reverse order
    # we keep the most current messages that are fresh enough to be relevant
    for msg in reversed(prev_messages):  # iterate in reverse order,
        msg_created_at = msg.created_at
        assert isinstance(msg_created_at, datetime)

        if most_recent_kept_message and most_recent_kept_message.role == TOOL:
            new_messages.appendleft(msg)
            current_token_count += count_tokens(msg.content)
            most_recent_kept_message = msg
            continue
        if current_token_count > context.config.context_refresh_token_target:
            break
        elif msg_created_at < get_utc_now() - timedelta(seconds=context.config.max_in_context_message_age_seconds):
            logging.info(f"Dropping old message {msg.id}")
            continue
        else:
            new_messages.appendleft(msg)
            current_token_count += count_tokens(msg.content)
            most_recent_kept_message = msg
    new_messages.appendleft(system_message)

    return list(new_messages)


def format_context_messages(user_preferred_name: str, context_messages: List[ContextMessage]) -> str:
    convo_range = pipe(
        context_messages,
        filter(lambda _: _.role == USER),
        map(lambda _: _.created_at),
        list,
        lambda l: f"Messages from {datetime_to_string(min(l))} to {datetime_to_string(max(l))}" if l else "No messages in context",
    )

    return (
        pipe(
            context_messages,
            map(lambda msg: format_message(user_preferred_name, msg)),
            remove(lambda _: _ is None),
            list,
            "\n".join,
            str,
        )
        + convo_range
    )  # type: ignore


def replace_system_message(context_messages: List[ContextMessage], new_system_message: ContextMessage) -> List[ContextMessage]:
    if not context_messages[0].role == "system":
        logging.warning(f"Expected system message to be first in context messages, but first message role is {context_messages[0].role}")
        return [new_system_message] + context_messages
    else:
        return [new_system_message] + context_messages[1:]


@logged_exec_time
async def context_refresh(context: ElroyContext) -> None:
    from ..repository.memory import create_memory, formulate_memory
    from ..tools.user_preferences import get_user_preferred_name

    context_messages = get_context_messages(context)
    user_preferred_name = get_user_preferred_name(context)

    # We calculate an archival memory, then persist it, then use it to calculate entity facts, then persist those.
    memory_title, memory_text = await formulate_memory(user_preferred_name, context_messages)
    create_memory(context, memory_title, memory_text)

    for mem1, mem2 in find_redundant_pairs(context, Memory):
        await consolidate_memories(context, mem1, mem2)

    pipe(
        get_refreshed_system_message(user_preferred_name, context_messages),
        partial(replace_system_message, context_messages),
        partial(compress_context_messages, context),
        partial(replace_context_messages, context),
    )


def remove_memory_from_context(memory_type: str, context: ElroyContext, memory_id: int) -> None:
    def is_memory_in_context_message(msg: ContextMessage) -> bool:
        if not msg.memory_metadata:
            return False

        return any(x.memory_type == memory_type and x.id == memory_id for x in msg.memory_metadata)

    pipe(
        get_context_messages(context),
        filter(is_memory_in_context_message),
        list,
        partial(remove_context_messages, context),
    )


def remove_from_context(context: ElroyContext, memory: EmbeddableSqlModel):
    id = memory.id
    assert id
    remove_memory_from_context(memory.__class__.__name__, context, id)


def add_to_context(context: ElroyContext, memory: EmbeddableSqlModel) -> None:
    memory_id = memory.id
    assert memory_id

    add_context_messages(
        context,
        [
            ContextMessage(
                role="system",
                memory_metadata=[MemoryMetadata(memory_type=memory.__class__.__name__, id=memory_id, name=memory.get_name())],
                content=str(to_fact(memory)),
            )
        ],
    )


def add_goal_to_current_context(context: ElroyContext, goal_name: str) -> str:
    """Adds goal with the given name to the current conversation context

    Args:
        context (ElroyContext): context obj
        goal_name (str): The name of the goal to add

    Returns:
        str: _description_
    """
    goal = context.session.exec(
        select(Goal).where(
            Goal.user_id == context.user_id,
            Goal.name == goal_name,
        )
    ).first()

    if goal:
        add_to_context(context, goal)
        return f"Goal '{goal_name}' added to context."
    else:
        return f"Goal {goal_name} not found."


def is_memory_in_context(context_messages: List[ContextMessage], memory: EmbeddableSqlModel) -> bool:
    return pipe(
        context_messages,
        map(lambda x: x.memory_metadata),
        filter(lambda x: x is not None),
        concat,
        filter(lambda x: x.memory_type == memory.__class__.__name__ and x.id == memory.id),
        list,
        lambda x: len(x) > 0,
    )


def drop_goal_from_current_context_only(context: ElroyContext, goal_name: str) -> str:
    """Drops the goal with the given name

    Args:
        context (ElroyContext): context obj
        goal_name (str): Name of the goal

    Returns:
        str: Information for the goal with the given name
    """

    goal = context.session.exec(
        select(Goal).where(
            Goal.user_id == context.user_id,
            Goal.name == goal_name,
        )
    ).first()
    if goal:
        remove_from_context(context, goal)
        return f"Goal '{goal_name}' dropped from context."

    else:
        return f"Goal '{goal_name}' not found for the current user."
