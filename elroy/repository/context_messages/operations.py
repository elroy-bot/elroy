import json
import time
import traceback
from functools import partial, wraps
from typing import Any, Callable, Iterable, Iterator, List, TypeVar

from sqlmodel import select
from toolz import concatv, pipe
from toolz.curried import tail

from ...config.paths import get_save_dir
from ...core.constants import (
    ASSISTANT,
    FORMATTING_INSTRUCT,
    SYSTEM,
    SYSTEM_INSTRUCTION_LABEL,
    SYSTEM_INSTRUCTION_LABEL_END,
    USER,
    user_only_tool,
)
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...core.tracing import tracer
from ...db.db_models import ContextMessageSet
from ...llm.prompts import summarize_conversation
from ...tools.inline_tools import inline_tool_instruct
from ...utils.clock import db_time_to_local
from ...utils.utils import run_in_background
from ..memories.operations import (
    create_mem_from_current_context,
    formulate_memory,
    get_or_create_memory_op_tracker,
)
from ..memories.tools import create_memory
from ..user.queries import do_get_user_preferred_name, get_assistant_name, get_persona
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

logger = get_logger()


def persist_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> Iterator[int]:
    for msg in messages:
        if not msg.content and not msg.tool_calls:
            logger.info(f"Skipping message with no content or tool calls: {msg}\n{traceback.format_exc()}")
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


T = TypeVar("T")


def retry_on_integrity_error(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(ctx: ElroyContext, *args: Any, **kwargs: Any) -> T:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return fn(ctx, *args, **kwargs)
            except Exception:
                if attempt == max_retries - 1:  # Last attempt
                    ctx.db.rollback()
                    raise
                else:
                    ctx.db.rollback()
                    time.sleep(0.1 * 2**attempt)
                    logger.info(f"Retrying on integrity error (attempt {attempt + 1}/{max_retries})")
        return fn(ctx, *args, **kwargs)

    return wrapper


@retry_on_integrity_error
def remove_context_messages(ctx: ElroyContext, messages: List[ContextMessage]) -> None:
    assert all(m.id is not None for m in messages), "All messages must have an id to be removed"

    msg_ids = [m.id for m in messages]
    replace_context_messages(ctx, [m for m in get_context_messages(ctx) if m.id not in msg_ids])


def add_context_message(ctx: ElroyContext, message: ContextMessage) -> None:
    add_context_messages(ctx, [message])


@retry_on_integrity_error
def add_context_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> None:
    msgs_list = list(messages)
    user_and_asst_msgs_ct = len([msg for msg in msgs_list if msg.role in {USER, ASSISTANT}])

    pipe(
        concatv(get_context_messages(ctx), msgs_list),
        partial(replace_context_messages, ctx),
    )

    if user_and_asst_msgs_ct > 0:
        tracker = get_or_create_memory_op_tracker(ctx)
        tracker.messages_since_memory += user_and_asst_msgs_ct
        ctx.db.add(tracker)
        ctx.db.commit()
        ctx.db.refresh(tracker)

        if tracker.messages_since_memory >= ctx.messages_between_memory:
            run_in_background(create_mem_from_current_context, ctx)


def get_refreshed_system_message(ctx: ElroyContext, context_messages_iter: Iterable[ContextMessage]) -> ContextMessage:

    context_messages = list(context_messages_iter)

    assert isinstance(context_messages, list)
    if len(context_messages) > 0 and context_messages[0].role == SYSTEM:
        # skip existing system message if it is still in context.
        context_messages = context_messages[1:]

    if len([msg for msg in context_messages if msg.role == USER]) == 0:
        conversation_summary = None
    else:
        assistant_name = get_assistant_name(ctx)

        conversation_summary = pipe(
            context_messages,
            lambda msgs: format_context_messages(
                msgs,
                do_get_user_preferred_name(ctx.db.session, ctx.user_id),
                assistant_name,
            ),
            partial(summarize_conversation, ctx.chat_model, assistant_name),
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


@tracer.agent
def context_refresh(ctx: ElroyContext, context_messages: Iterable[ContextMessage]) -> None:
    logger.info("Refreshing context")
    context_message_list = list(context_messages)

    # We calculate an archival memory, then persist it, then use it to calculate entity facts, then persist those.
    memory_title, memory_text = formulate_memory(ctx, context_message_list)
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
        context_refresh(ctx, context_messages)


@user_only_tool
def save(ctx: ElroyContext, n: int = 1000) -> str:
    """
    Saves the last n message from context.
    """

    msgs = pipe(
        get_context_messages(ctx),
        tail(n),
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
        replace_context_messages(ctx, context_messages)
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
    logger.info("Resetting messages: Dropping all conversation messages and recalculating system message")

    replace_context_messages(
        ctx,
        [get_refreshed_system_message(ctx, [])],
    )

    return "Context reset complete"
