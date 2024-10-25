import logging
from collections import deque
from datetime import timedelta
from functools import partial, reduce
from operator import add
from typing import List, Optional

from tiktoken import encoding_for_model
from toolz import pipe
from toolz.curried import filter, map, remove

from elroy.config import ElroyContext
from elroy.llm.prompts import persona, summarize_conversation
from elroy.memory import consolidate_memories
from elroy.store.data_models import ASSISTANT, TOOL, USER, ContextMessage, Memory
from elroy.store.embeddings import find_redundant_pairs
from elroy.store.message import (get_context_messages,
                                 get_time_since_context_message_creation,
                                 replace_context_messages)
from elroy.system.clock import get_utc_now
from elroy.system.parameters import CHAT_MODEL
from elroy.system.utils import logged_exec_time, utc_epoch_to_datetime_string


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
    datetime_str = utc_epoch_to_datetime_string(message.created_at_utc_epoch_secs)
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


@logged_exec_time
def context_refresh_if_needed(context: ElroyContext):
    if is_context_refresh_needed(context):
        logging.info(f"Refreshing context for user id {context.user_id}")
        context_refresh(context)


def compress_context_messages(context: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    """Refreshes context, saving to archival memory and compressing the context window."""

    system_message, prev_messages = context_messages[0], context_messages[1:]

    new_messages = deque()
    current_token_count = count_tokens(system_message.content)
    most_recent_kept_message = None  # we will keep track of what message we last decided to keep

    # iterate through non-system context messages in reverse order
    # we keep the most current messages that are fresh enough to be relevant
    for msg in reversed(prev_messages):  # iterate in reverse order,
        msg_created_at_utc_epoch_secs = msg.created_at_utc_epoch_secs
        assert isinstance(msg_created_at_utc_epoch_secs, float)

        if most_recent_kept_message and most_recent_kept_message.role == TOOL:
            new_messages.appendleft(msg)
            current_token_count += count_tokens(msg.content)
            most_recent_kept_message = msg
            continue
        if current_token_count > context.config.context_refresh_token_target:
            break
        elif msg_created_at_utc_epoch_secs < get_utc_now().timestamp() - context.config.max_in_context_message_age_seconds:
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
        map(lambda _: _.created_at_utc_epoch_secs),
        list,
        lambda l: f"Messages from {utc_epoch_to_datetime_string(min(l))} to {utc_epoch_to_datetime_string(max(l))}",
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
def context_refresh(context: ElroyContext) -> None:
    from elroy.memory import create_memory, formulate_memory
    from elroy.tools.functions.user_preferences import get_user_preferred_name

    context_messages = get_context_messages(context)
    user_preferred_name = get_user_preferred_name(context)

    # We calculate an archival memory, then persist it, then use it to calculate entity facts, then persist those.
    pipe(
        formulate_memory(user_preferred_name, context_messages),
        lambda response: create_memory(context, response[0], response[1]),
    )

    for mem1, mem2 in find_redundant_pairs(context, Memory):
        consolidate_memories(context, mem1, mem2)

    pipe(
        get_refreshed_system_message(user_preferred_name, context_messages),
        partial(replace_system_message, context_messages),
        partial(compress_context_messages, context),
        partial(replace_context_messages, context),
    )
