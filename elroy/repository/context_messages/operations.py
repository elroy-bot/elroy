import json
import time
import traceback
from collections.abc import Callable, Iterable, Iterator
from functools import partial, wraps
from typing import Any, TypeVar

from toolz import pipe
from toolz.curried import tail

from ...config.paths import get_save_dir
from ...core.constants import (
    ASSISTANT,
    FORMATTING_INSTRUCT,
    SYSTEM,
    SYSTEM_INSTRUCTION_LABEL,
    SYSTEM_INSTRUCTION_LABEL_END,
    user_only_tool,
)
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from ...core.services.context_message_service import (
    ContextMessageOperationService,
    context_message_operation_service_for_context,
)
from ...core.tracing import tracer
from ...llm.prompts import summarize_conversation
from ...tools.inline_tools import inline_tool_instruct
from ...utils.clock import db_time_to_local, utc_now
from ..memories.operations import (
    formulate_memory,
)
from ..memories.tools import create_memory
from ..user.queries import assistant_name_for_user, do_get_user_preferred_name, persona_for_user
from .data_models import ContextMessage
from .queries import get_context_messages
from .tools import to_synthetic_tool_call
from .transforms import (
    compress_context_messages,
    format_context_messages,
    is_context_refresh_needed,
    remove,
)

logger = get_logger()


def context_message_operation_service(ctx: ElroyContext) -> ContextMessageOperationService:
    return context_message_operation_service_for_context(ctx)


def persist_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> Iterator[int]:
    for msg in messages:
        if not msg.content and not msg.tool_calls:
            logger.info(f"Skipping message with no content or tool calls: {msg}\n{traceback.format_exc()}")
        else:
            yield from context_message_operation_service(ctx).persist_messages([msg])


def replace_context_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> None:
    context_message_operation_service(ctx).replace_context_messages(messages)


T = TypeVar("T")


def retry_on_integrity_error[T](fn: Callable[..., T]) -> Callable[..., T]:
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
                ctx.db.rollback()
                time.sleep(0.1 * 2**attempt)
                logger.info(f"Retrying on integrity error (attempt {attempt + 1}/{max_retries})")
        return fn(ctx, *args, **kwargs)

    return wrapper


@retry_on_integrity_error
def remove_context_messages(ctx: ElroyContext, messages: list[ContextMessage]) -> None:
    if not messages:
        return
    logger.info(f"Removing {len(messages)} messages")
    context_message_operation_service(ctx).remove_context_messages(messages)


def add_context_message(ctx: ElroyContext, message: ContextMessage) -> None:
    add_context_messages(ctx, [message])


@retry_on_integrity_error
def add_context_messages(ctx: ElroyContext, messages: Iterable[ContextMessage]) -> None:
    context_message_operation_service(ctx).add_context_messages(messages)


def get_refreshed_system_message(ctx: ElroyContext) -> ContextMessage:
    """
    Generate stable system message WITHOUT conversational summary.
    System message should be stable across normal operations to preserve prompt cache.
    """

    # Generate stable system message without conversational summary to preserve prompt cache.
    # Summary is added separately in context_refresh() to avoid invalidating the cache.
    # System message only changes when persona, tools, or formatting instructions change.

    return pipe(
        [
            SYSTEM_INSTRUCTION_LABEL,
            f"<persona>{persona_for_user(ctx.db.session, ctx.user_id, ctx.default_persona, ctx.default_assistant_name)}</persona>",
            FORMATTING_INSTRUCT,
            inline_tool_instruct(ctx.tool_registry.get_schemas()) if ctx.chat_model.inline_tool_calls else None,
            "From now on, converse as your persona.",
            SYSTEM_INSTRUCTION_LABEL_END,
        ],
        remove(lambda _: _ is None),
        list,
        "\n".join,
        lambda x: ContextMessage(role=SYSTEM, content=x, chat_model=None),
    )


def context_refresh(ctx: ElroyContext, context_messages: Iterable[ContextMessage]) -> None:
    """
    Refresh context WITHOUT regenerating system message to preserve prompt cache.

    Cache-friendly approach:
    1. Keep existing system message (preserves cache)
    2. Compress messages
    3. Add conversational summary as synthetic tool call (appended, doesn't break cache)
    """
    logger.info("Refreshing context (cache-friendly: preserving system message)")
    context_message_list = list(context_messages)

    # We calculate an archival memory, then persist it, then use it to calculate entity facts, then persist those.
    memory_title, memory_text = formulate_memory(ctx, context_message_list)
    create_memory(ctx, memory_title, memory_text)

    # Compress messages while keeping existing system message
    compressed_messages = pipe(
        context_message_list,
        partial(
            compress_context_messages,
            ctx.chat_model.name,
            ctx.context_refresh_target_tokens,
            ctx.max_in_context_message_age,
        ),
    )

    # Generate conversational summary from context (excluding system message)
    # This provides context continuity without breaking the cache
    if len([msg for msg in context_message_list if msg.role == USER]) > 0:
        assistant_name = assistant_name_for_user(ctx.db.session, ctx.user_id, ctx.default_assistant_name)

        conversation_summary = pipe(
            context_message_list[1:],  # Skip system message
            lambda msgs: format_context_messages(
                msgs,
                do_get_user_preferred_name(ctx.db.session, ctx.user_id),
                assistant_name,
            ),
            partial(summarize_conversation, ctx.fast_llm, assistant_name),
        )

        # Create synthetic tool call with the summary (cache-friendly: appended at end)
        summary_tool_call = to_synthetic_tool_call(
            func_name="context_summary",
            func_response=f"Recent conversation summary: {conversation_summary}",
        )

        # Replace context with: compressed messages + summary tool call
        replace_context_messages(ctx, compressed_messages + summary_tool_call)
    else:
        # No user messages yet, just use compressed messages
        replace_context_messages(ctx, compressed_messages)


def drop_old_context_messages(ctx: ElroyContext) -> None:
    now = utc_now()
    context_messages = list(get_context_messages(ctx))
    to_keep = [m for m in context_messages if m.role == SYSTEM or not m.created_at or m.created_at >= now - ctx.max_in_context_message_age]
    if len(to_keep) < len(context_messages):
        logger.info(f"Dropping {len(context_messages) - len(to_keep)} messages older than {ctx.max_in_context_message_age}")
        replace_context_messages(ctx, to_keep)


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

    filename = (
        db_time_to_local(msgs[0].created_at).strftime("%Y-%m-%d_%H-%M-%S")
        + "__"
        + db_time_to_local(msgs[-1].created_at).strftime("%Y-%m-%d_%H-%M-%S")
        + ".json"
    )
    full_path = get_save_dir() / filename

    with full_path.open("w") as f:
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
            get_refreshed_system_message(ctx),
        )
    else:
        context_messages[0] = get_refreshed_system_message(ctx)
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
        [get_refreshed_system_message(ctx)],
    )

    return "Context reset complete"
