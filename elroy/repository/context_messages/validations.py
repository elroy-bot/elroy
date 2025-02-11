import logging
from functools import partial
from typing import List

from toolz import pipe

from ...config.constants import (
    ASSISTANT,
    TOOL,
    USER,
    MissingAssistantToolCallError,
    MissingToolCallMessageError,
)
from ...config.ctx import ElroyContext
from .data_models import ContextMessage
from .inspect import has_assistant_tool_call
from .operations import get_refreshed_system_message, replace_context_messages
from .transforms import is_system_instruction


def validate_assistant_tool_calls_followed_by_tool(debug_mode: bool, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    """
    Validates that any assistant message with non-empty tool_calls is followed by corresponding tool messages.
    """

    for idx, message in enumerate(context_messages):
        if (message.role == ASSISTANT and message.tool_calls is not None) and (
            idx == len(context_messages) - 1 or context_messages[idx + 1].role != TOOL
        ):
            if debug_mode:
                raise MissingToolCallMessageError()
            else:
                logging.error(
                    f"Assistant message with tool_calls not followed by tool message: ID = {message.id}, repairing by removing tool_calls"
                )
                message.tool_calls = None
    return context_messages


def validate_tool_messages_have_assistant_tool_call(debug_mode: bool, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    """
    Validates that all tool messages have a preceding assistant message with the corresponding tool_calls.
    """

    validated_context_messages = []
    for idx, message in enumerate(context_messages):
        if message.role == TOOL and not has_assistant_tool_call(message.tool_call_id, context_messages[:idx]):
            if debug_mode:
                raise MissingAssistantToolCallError(f"Message id: {message.id}")
            else:
                logging.warning(
                    f"Tool message without preceding assistant message with tool_calls: ID = {message.id}. Repairing by removing tool message"
                )
                continue
        else:
            validated_context_messages.append(message)

    return validated_context_messages


def validate_system_instruction_correctly_placed(ctx: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    validated_messages = []
    for idx, message in enumerate(context_messages):
        if idx == 0 and not is_system_instruction(message):
            logging.info(f"First message is not system instruction, repairing by inserting system instruction")
            validated_messages += [
                get_refreshed_system_message(ctx, context_messages),
                message,
            ]
        elif idx != 0 and is_system_instruction(message):
            logging.error("Found system message in non-first position, repairing by dropping message")
            continue
        else:
            validated_messages.append(message)
    return validated_messages


def validate_first_user_precedes_first_assistant(context_messages: List[ContextMessage]) -> List[ContextMessage]:
    user_and_assistant_messages = [m for m in context_messages if m.role in [USER, ASSISTANT]]

    if user_and_assistant_messages and user_and_assistant_messages[0].role != USER:
        logging.info("First non-system message is not user message, repairing by inserting user message")

        context_messages = [
            context_messages[0],
            ContextMessage(role=USER, content="The user has begun the converstaion", chat_model=None),
        ] + context_messages[1:]
    return context_messages


def validate(ctx: ElroyContext, context_messages: List[ContextMessage]) -> List[ContextMessage]:
    messages = pipe(
        context_messages,
        partial(validate_system_instruction_correctly_placed, ctx),
        partial(validate_assistant_tool_calls_followed_by_tool, ctx.debug),
        partial(validate_tool_messages_have_assistant_tool_call, ctx.debug),
        lambda msgs: (msgs if not ctx.chat_model.ensure_alternating_roles else validate_first_user_precedes_first_assistant(msgs)),
        list,
    )

    if messages != context_messages:
        logging.info("Context messages have been repaired")
        replace_context_messages(ctx, messages)
    return messages
