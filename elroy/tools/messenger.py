import json
import logging
from dataclasses import asdict
from functools import partial
from typing import List

from sqlmodel import Session
from toolz import assoc, concat, juxt, pipe
from toolz.curried import do, filter, map, remove

from elroy.llm.client import (MissingToolCallIdError,
                              generate_chat_completion_message, get_embedding,
                              query_llm)
from elroy.memory.system_context import get_internal_though_monologue
from elroy.store.data_models import EmbeddableSqlModel
from elroy.store.embeddings import (get_most_relevant_archival_memory,
                                    get_most_relevant_entity,
                                    get_most_relevant_goal)
from elroy.store.message import (ContextMessage, MemoryMetadata,
                                 get_context_messages,
                                 replace_context_messages)
from elroy.system.parameters import (MEMORY_PROCESSING_MODEL,
                                     MESSAGE_LENGTH_WORDS_GUIDANCE)
from elroy.system.utils import last_or_none, logged_exec_time
from elroy.tools.function_caller import (ERROR_PREFIX, FunctionCall,
                                         exec_function_call)
from elroy.tools.system_commands import (invoke_system_command,
                                         is_system_command)
from elroy.ui.loading_message import cli_loading


def process_message(session: Session, user_id: int, msg: str) -> str:
    """Process a message from a user. Includes persistence, and any system edits

    Args:
        user_id (int): _description_
        msg (str): Message from user
        delivery_fun (Callable): Function which will delivery the message to the user
        message_preprocessing_fn (Callable, optional): Any alteration that should happen to the message before persistence / processing. Defaults to identity.

    Returns:
        str: The response to the message
    """

    if is_system_command(msg):
        return invoke_system_command(session, user_id, msg)
    else:
        context_messages = pipe(
            get_context_messages(session, user_id) + [ContextMessage(role="user", content=msg)],
            partial(append_relevant_memories, session, user_id),
            partial(_generate_assistant_reply, session, user_id),
            do(partial(replace_context_messages, session, user_id)),
        )

        assert context_messages[-1].role == "assistant"

        content = context_messages[-1].content
        assert content is not None

        return content


def edit_message_for_length(character_length_limit: int, response: str) -> str:
    new_response = query_llm(
        model=MEMORY_PROCESSING_MODEL,
        system="Your job is to edit a response from the assistant to a user. The response is too long and needs to be shortened."
        f"The length of the response should not exceed {MESSAGE_LENGTH_WORDS_GUIDANCE - 25} words."
        "Only output the edited response, do NOT include anything else in your output."
        "If xml tags are present, preserve formatting",
        prompt=response,
    )

    if len(new_response) < character_length_limit:
        return new_response
    else:
        logging.error(f"Response is too long, truncating")
        return new_response[:character_length_limit]


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


@cli_loading("Searching for relevant memories...")
@logged_exec_time
def append_relevant_memories(session: Session, user_id: int, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    last_user_message_content = pipe(
        context_messages,
        filter(lambda _: _.role == "user"),
        last_or_none,
        lambda m: m.content if m else None,
    )

    if not last_user_message_content:
        return context_messages

    assert isinstance(last_user_message_content, str)

    return pipe(
        last_user_message_content,
        get_embedding,
        lambda x: juxt(get_most_relevant_goal, get_most_relevant_archival_memory, get_most_relevant_entity)(session, user_id, x),
        filter(lambda x: x is not None),
        remove(partial(is_memory_in_context, context_messages)),
        map(
            lambda x: ContextMessage(
                role="system",
                memory_metadata=[MemoryMetadata(memory_type=x.__class__.__name__, id=x.id, name=x.get_name())],
                content=get_internal_though_monologue(last_user_message_content, x),
            )
        ),
        list,
        lambda x: context_messages + x,
    )


def _generate_assistant_reply(
    session: Session,
    user_id: int,
    context_messages: List[ContextMessage],
    recursion_count: int = 0,
) -> List[ContextMessage]:
    """
    Fetch current in context messages, generate a chat completion

    If the last message in context is from a user, we need to generate an assistant message

    If the last message in the context is from a tool, we need to generate a user message to
    prompt the assistant to message the user. This should not prompt further tool calls.

    If the last message in the context is from the assistant, we are finished and can return.
    """

    if recursion_count >= 10:
        raise ValueError("Exceeded maximum number of chat completion attempts")
    elif recursion_count > 0:
        logging.info(f"Recursion count: {recursion_count}")

    if context_messages[-1].role == "assistant":
        return context_messages

    try:
        llm_response = generate_chat_completion_message([asdict(x) for x in context_messages])

        assert llm_response.content or llm_response.tool_calls

        assistant_reply = ContextMessage(
            role="assistant",
            content=llm_response.content,
            tool_calls=(
                None
                if not llm_response.tool_calls
                else pipe(
                    llm_response.tool_calls,
                    map(dict),
                    map(lambda _: assoc(_, "function", dict(_["function"]))),
                    list,
                )
            ),  # type: ignore
        )

        context_messages += [assistant_reply]

        if llm_response.tool_calls:
            context_messages += pipe(
                llm_response.tool_calls,
                map(
                    lambda x: FunctionCall(
                        id=x.id,
                        user_id=user_id,
                        function_name=x.function.name,
                        arguments=json.loads(x.function.arguments),
                    )
                ),  # type: ignore
                map(
                    lambda x: ContextMessage(
                        role="tool",
                        tool_call_id=x.id,
                        content=exec_function_call(session, user_id, x),
                    )
                ),
                list,
            )

            if context_messages[-1].content and context_messages[-1].content.startswith(ERROR_PREFIX):
                return _generate_assistant_reply(
                    session,
                    user_id,
                    context_messages
                    + [
                        ContextMessage(
                            role="system", content="There was an error in the tool call. Please report on the error to the user."
                        )
                    ],
                    recursion_count + 1,
                )
            else:
                # TODO: Do we actually need to add a message?
                return _generate_assistant_reply(
                    session,
                    user_id,
                    context_messages
                    + [ContextMessage(role="system", content="The results of your function call are ready. Please respond to the user.")],
                    recursion_count + 1,
                )

    except MissingToolCallIdError:
        # Any assistant messages with a tool call id must be followed by a tool call message with the corresponding id
        # Sometimes this gets fumbled, e.g. if execution is interupted
        # To fix, we drop any assistant messages with tools calls where corresponding subsequent tool message(s) is/are missing.
        logging.error("Attempting to repair missing tool call ID")

        # Scan messages from most recent to oldest.

        new_context_messages = []
        for msg in reversed(context_messages):
            if msg != "assistant" or not msg.tool_calls:
                new_context_messages = [msg] + new_context_messages
            else:
                for tool_call in msg.tool_calls:
                    if any(m.tool_call_id == tool_call.id for m in new_context_messages):
                        new_context_messages = [msg] + new_context_messages
                    else:
                        logging.error(f"Dropping assistant message without corresponding tool call message. ID: {msg.id}")
                        continue
        if len(context_messages) == len(new_context_messages):
            raise ValueError("Could not repair missing tool call ID")
        logging.error(f"Dropping {len(context_messages) - len(new_context_messages)} context messages for user {user_id}")
        context_messages = new_context_messages

    if context_messages[-1].role == "assistant":
        return context_messages
    else:
        return _generate_assistant_reply(
            session,
            user_id,
            context_messages,
            recursion_count + 1,
        )
