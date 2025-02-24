import json
import logging
import traceback
from functools import partial
from typing import Iterable, Iterator, List, Optional

from sqlmodel import select
from toolz import concatv, pipe
from toolz.curried import tail

from ...config.constants import (
    ASSISTANT,
    FORMATTING_INSTRUCT,
    SYSTEM,
    SYSTEM_INSTRUCTION_LABEL,
    SYSTEM_INSTRUCTION_LABEL_END,
    USER,
    user_only_tool,
)
from ...config.ctx import ElroyContext
from ...config.paths import get_save_dir
from ...db.db_models import ContextMessageSet
from ...llm.prompts import summarize_conversation
from ...tools.inline_tools import inline_tool_instruct
from ...utils.clock import db_time_to_local
from ...utils.utils import logged_exec_time, run_async
from ..memories.operations import formulate_memory
from ..memories.tools import create_memory
from ..user.operations import get_or_create_user_preference
from ..user.queries import do_get_user_preferred_name, get_persona
from .data_models import ContextMessage
from .queries import get_context_messages
from .transforms import (
    compress_context_messages,
    context_message_to_db_message,
    format_context_messages,
    is_context_refresh_needed,
    remove,
    replace_system_instruction,
)


def persist_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> Iterator[int]:
    for msg in messages:
        if not msg.content and not msg.tool_calls:
            logging.info(f"Skipping message with no content or tool calls: {msg}\n{traceback.format_exc()}")
        elif msg.id:
            yield msg.id
        else:
            db_message = context_message_to_db_message(ctx.user_id, msg)
            ctx.db.add(db_message)
            ctx.db.commit()
            ctx.db.refresh(db_message)
            assert db_message.id
            yield db_message.id


def replace_context_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> None:
    # Dangerous! The message set might have been updated since we fetched it
    msg_ids = list(persist_messages(ctx, messages))

    existing_context = ctx.db.exec(
        select(ContextMessageSet).where(
            ContextMessageSet.user_id == ctx.user_id,
            ContextMessageSet.is_active == True,
        )
    ).first()

    if existing_context:
        existing_context.is_active = None
        ctx.db.add(existing_context)
    new_context = ContextMessageSet(
        user_id=ctx.user_id,
        message_ids=json.dumps(msg_ids),
        is_active=True,
    )
    ctx.db.add(new_context)
    ctx.db.commit()


def remove_context_messages(ctx: ElroyContext, messages: List[ContextMessage]) -> None:
    assert all(m.id is not None for m in messages), "All messages must have an id to be removed"

    msg_ids = [m.id for m in messages]

    replace_context_messages(ctx, [m for m in get_context_messages(ctx) if m.id not in msg_ids])


def add_context_message(ctx: ElroyContext, message: ContextMessage) -> None:
    add_context_messages(ctx, [message])


def add_context_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> None:
    pipe(
        concatv(get_context_messages(ctx), messages),
        partial(replace_context_messages, ctx),
    )


def get_refreshed_system_message(ctx: ElroyContext, context_messages_iter: Iterable[ContextMessage]) -> ContextMessage:
    user_preference = get_or_create_user_preference(ctx)

    context_messages = list(context_messages_iter)

    assert isinstance(context_messages, list)
    if len(context_messages) > 0 and context_messages[0].role == SYSTEM:
        # skip existing system message if it is still in context.
        context_messages = context_messages[1:]

    if len([msg for msg in context_messages if msg.role == USER]) == 0:
        conversation_summary = None
    else:
        conversation_summary = pipe(
            context_messages,
            lambda msgs: format_context_messages(msgs, user_preference.preferred_name),
            partial(summarize_conversation, ctx.chat_model),
            lambda _: f"<conversational_summary>{_}</conversational_summary>",
            str,
        )

    return pipe(
        [
            SYSTEM_INSTRUCTION_LABEL,
            f"<persona>{get_persona(ctx)}</persona>",
            conversation_summary,
            FORMATTING_INSTRUCT,
            inline_tool_instruct(ctx.tool_registry.get_schemas()) if ctx.chat_model.inline_tool_calls else None,
            "From now on, converse as your persona.",
            SYSTEM_INSTRUCTION_LABEL_END,
        ],  # type: ignore
        remove(lambda _: _ is None),
        list,
        "\n".join,
        lambda x: ContextMessage(role=SYSTEM, content=x, chat_model=None),
    )


@logged_exec_time
def context_refresh(ctx: ElroyContext, context_messages: Iterable[ContextMessage]) -> None:
    context_message_list = list(context_messages)

    user_preferred_name = do_get_user_preferred_name(ctx.db.session, ctx.user_id)

    # We calculate an archival memory, then persist it, then use it to calculate entity facts, then persist those.
    memory_title, memory_text = formulate_memory(ctx.chat_model, user_preferred_name, context_message_list)
    create_memory(ctx, memory_title, memory_text)

    pipe(
        get_refreshed_system_message(ctx, context_message_list),
        partial(replace_system_instruction, context_message_list),
        partial(
            compress_context_messages,
            ctx.chat_model.name,
            ctx.context_refresh_target_tokens,
            ctx.max_in_context_message_age,
        ),
        partial(replace_context_messages, ctx),
    )


def refresh_context_if_needed(ctx: ElroyContext):
    context_messages = list(get_context_messages(ctx))
    if is_context_refresh_needed(context_messages, ctx.chat_model.name, ctx.max_tokens):
        run_async(
            ctx.thread_pool,
            context_refresh(ctx, context_messages),
        )


@user_only_tool
def save(ctx: ElroyContext, n: Optional[int]) -> str:
    """
    Saves the last n message from context. If n is None, saves all messages in context.
    """

    msgs = pipe(
        get_context_messages(ctx),
        tail(n or 1000),
        list,
    )

    filename = db_time_to_local(msgs[0].created_at).strftime("%Y-%m-%d_%H-%M-%S") + "__" + db_time_to_local(msgs[-1].created_at).strftime("%Y-%m-%d_%H-%M-%S") + ".json"  # type: ignore
    full_path = get_save_dir() / filename

    with open(full_path, "w") as f:
        f.write(json.dumps([msg.as_dict() for msg in msgs]))
    return "Saved messages to " + str(full_path)


@user_only_tool
def pop(ctx: ElroyContext, n: int) -> str:
    """
    Removes the last n messages from the context

    Args:
        n (int): The number of messages to remove

    Returns:
       str: The result of the pop operation.
    """
    original_list = list(get_context_messages(ctx))

    if n <= 0:
        return "Cannot pop 0 or fewer messages"
    if n > len(original_list):
        return f"Cannot pop {n} messages, only {len(original_list)} messages in context"
    context_messages = original_list[:-n]

    if context_messages[-1].role == ASSISTANT and context_messages[-1].tool_calls:
        return f"Popping {n} message would separate an assistant message with a tool call from the tool result. Please pop fewer or more messages."

    else:
        replace_context_messages(ctx, context_messages[:-n])
        return f"Popped {n} messages from context, new context has {len(list(get_context_messages(ctx)))} messages"


@user_only_tool
def rewrite(ctx: ElroyContext, new_message: str) -> str:
    """
    Replaces the last message assistant in the context with the new message
        new_message (str): The new message to replace the last message with

    Returns:
        str: The result of the rewrite operation
    """
    if not new_message:
        return "Cannot rewrite message with empty message"

    context_messages = list(get_context_messages(ctx))
    if len(context_messages) == 0:
        return "No messages to rewrite"

    i = -1
    while context_messages[i].role != ASSISTANT:
        i -= 1

    context_messages[i] = ContextMessage(role=ASSISTANT, content=new_message, chat_model=None)

    replace_context_messages(ctx, context_messages)

    return "Replaced last assistant message with new message"


@user_only_tool
def refresh_system_instructions(ctx: ElroyContext) -> str:
    """Refreshes the system instructions

    Args:
        user_id (_type_): user id

    Returns:
        str: The result of the system instruction refresh
    """

    context_messages = list(get_context_messages(ctx))
    if len(context_messages) == 0:
        context_messages.append(
            get_refreshed_system_message(ctx, []),
        )
    else:
        context_messages[0] = get_refreshed_system_message(
            ctx,
            context_messages[1:],
        )
    replace_context_messages(ctx, context_messages)
    return "System instruction refresh complete"


@user_only_tool
def reset_messages(ctx: ElroyContext) -> str:
    """Resets the context for the user, removing all messages from the context except the system message.
    This should be used sparingly, only at the direct request of the user.

    Args:
        user_id (int): user id

    Returns:
        str: The result of the context reset
    """
    logging.info("Resetting messages: Dropping all conversation messages and recalculating system message")

    replace_context_messages(
        ctx,
        [get_refreshed_system_message(ctx, [])],
    )

    return "Context reset complete"
