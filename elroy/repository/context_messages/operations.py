import json
import logging
import traceback
from functools import partial
from typing import List, Optional, Union

from sqlmodel import select
from toolz import pipe, tail

from ...config.constants import (
    ASSISTANT,
    FORMATTING_INSTRUCT,
    SYSTEM,
    SYSTEM_INSTRUCTION_LABEL,
    SYSTEM_INSTRUCTION_LABEL_END,
    USER,
    tool,
)
from ...config.ctx import ElroyContext
from ...config.paths import get_save_dir
from ...db.db_models import ContextMessageSet, Goal, Memory
from ...llm.prompts import summarize_conversation
from ...tools.inline_tools import inline_tool_instruct
from ...utils.clock import db_time_to_local
from ...utils.utils import do_asyncio_run, logged_exec_time
from ..memories.operations import create_memory, formulate_memory
from ..user.operations import get_or_create_user_preference
from ..user.queries import get_persona, get_user_preferred_name
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


def persist_messages(ctx: ElroyContext, messages: List[ContextMessage]) -> List[int]:
    msg_ids = []
    for msg in messages:
        if not msg.content and not msg.tool_calls:
            logging.warning(f"Skipping message with no content or tool calls: {msg}\n{traceback.format_exc()}")
        elif msg.id:
            msg_ids.append(msg.id)
        else:
            db_message = context_message_to_db_message(ctx.user_id, msg)
            ctx.db.add(db_message)
            ctx.db.commit()
            ctx.db.refresh(db_message)
            msg_ids.append(db_message.id)
    return msg_ids


def replace_context_messages(ctx: ElroyContext, messages: List[ContextMessage]) -> None:
    # Dangerous! The message set might have been updated since we fetched it
    msg_ids = persist_messages(ctx, messages)

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


def add_context_messages(ctx: ElroyContext, messages: Union[ContextMessage, List[ContextMessage]]) -> None:
    pipe(
        messages,
        lambda x: x if isinstance(x, List) else [x],
        lambda x: get_context_messages(ctx) + x,
        partial(replace_context_messages, ctx),
    )


@tool
def add_memory_to_current_context(ctx: ElroyContext, memory_name: str) -> str:
    """Adds memory with the given name to the current conversation context.

    Args:
        memory_name (str): The name of the memory to add to context

    Returns:
        str: Status message indicating success or failure of adding memory
    """
    from ..recall.operations import add_to_current_context_by_name

    return add_to_current_context_by_name(ctx, memory_name, Memory)


@tool
def add_goal_to_current_context(ctx: ElroyContext, goal_name: str) -> str:
    """Adds goal with the given name to the current conversation context.

    Args:
        goal_name (str): The name of the goal to add to context

    Returns:
        str: Status message indicating success or failure of adding goal
    """

    from ..recall.operations import add_to_current_context_by_name

    return add_to_current_context_by_name(ctx, goal_name, Goal)


@tool
def drop_goal_from_current_context(ctx: ElroyContext, goal_name: str) -> str:
    """Drops the goal with the given name from current context. Does NOT delete or mark the goal completed.

    Args:
        goal_name (str): Name of the goal to remove from context

    Returns:
        str: Status message indicating success or failure of removing goal
    """
    from ..recall.operations import drop_from_context_by_name

    return drop_from_context_by_name(ctx, goal_name, Goal)


@tool
def drop_memory_from_current_context(ctx: ElroyContext, memory_name: str) -> str:
    """Drops the memory with the given name from current context. Does NOT delete the memory.

    Args:
        memory_name (str): Name of the memory to remove from context

    Returns:
        str: Status message indicating success or failure of removing memory
    """
    from ..recall.operations import drop_from_context_by_name

    return drop_from_context_by_name(ctx, memory_name, Memory)


def get_refreshed_system_message(ctx: ElroyContext, context_messages: List[ContextMessage]) -> ContextMessage:
    user_preference = get_or_create_user_preference(ctx)

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


def context_refresh_sync(ctx: ElroyContext, context_messages: List[ContextMessage]):
    do_asyncio_run(context_refresh(ctx, context_messages))


@logged_exec_time
async def context_refresh(ctx: ElroyContext, context_messages: List[ContextMessage]) -> None:

    user_preferred_name = get_user_preferred_name(ctx)

    # We calculate an archival memory, then persist it, then use it to calculate entity facts, then persist those.
    memory_title, memory_text = await formulate_memory(ctx.chat_model, user_preferred_name, context_messages)
    create_memory(ctx, memory_title, memory_text)

    pipe(
        get_refreshed_system_message(ctx, context_messages),
        partial(replace_system_instruction, context_messages),
        partial(
            compress_context_messages,
            ctx.chat_model.name,
            ctx.context_refresh_target_tokens,
            ctx.max_in_context_message_age,
        ),
        partial(replace_context_messages, ctx),
    )


def refresh_context_if_needed(ctx: ElroyContext):
    context_messages = get_context_messages(ctx)
    if is_context_refresh_needed(context_messages, ctx.chat_model.name, ctx.max_tokens):
        do_asyncio_run(context_refresh(ctx, context_messages))


def save(ctx: ElroyContext, n: Optional[int]) -> str:
    """
    Saves the last n message from context. If n is None, saves all messages in context.
    """

    msgs = pipe(
        get_context_messages(ctx),
        lambda x: tail(n, x) if n is not None else x,
        list,
        list,
    )

    filename = db_time_to_local(msgs[0].created_at).strftime("%Y-%m-%d_%H-%M-%S") + "__" + db_time_to_local(msgs[-1].created_at).strftime("%Y-%m-%d_%H-%M-%S") + ".json"  # type: ignore
    full_path = get_save_dir() / filename

    with open(full_path, "w") as f:
        f.write(json.dumps([msg.as_dict() for msg in msgs]))
    return "Saved messages to " + str(full_path)


def pop(ctx: ElroyContext, n: int) -> str:
    """
    Removes the last n messages from the context

    Args:
        n (int): The number of messages to remove

    Returns:
       str: The result of the pop operation.
    """
    if n <= 0:
        return "Cannot pop 0 or fewer messages"
    if n > len(get_context_messages(ctx)):
        return f"Cannot pop {n} messages, only {len(get_context_messages(ctx))} messages in context"
    context_messages = get_context_messages(ctx)[:-n]

    if context_messages[-1].role == ASSISTANT and context_messages[-1].tool_calls:
        return f"Popping {n} message would separate an assistant message with a tool call from the tool result. Please pop fewer or more messages."

    else:
        replace_context_messages(ctx, context_messages[:-n])
        return f"Popped {n} messages from context, new context has {len(get_context_messages(ctx))} messages"


def rewrite(ctx: ElroyContext, new_message: str) -> str:
    """
    Replaces the last message assistant in the context with the new message
        new_message (str): The new message to replace the last message with

    Returns:
        str: The result of the rewrite operation
    """
    if not new_message:
        return "Cannot rewrite message with empty message"

    context_messages = get_context_messages(ctx)
    if len(context_messages) == 0:
        return "No messages to rewrite"

    i = -1
    while context_messages[i].role != ASSISTANT:
        i -= 1

    context_messages[i] = ContextMessage(role=ASSISTANT, content=new_message, chat_model=None)

    replace_context_messages(ctx, context_messages)

    return "Replaced last assistant message with new message"


def refresh_system_instructions(ctx: ElroyContext) -> str:
    """Refreshes the system instructions

    Args:
        user_id (_type_): user id

    Returns:
        str: The result of the system instruction refresh
    """

    context_messages = get_context_messages(ctx)
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
