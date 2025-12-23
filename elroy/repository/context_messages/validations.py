from typing import Generator, Iterable, List

from toolz import identity, pipe

from ...core.constants import ASSISTANT, TOOL, USER
from ...core.ctx import ElroyContext
from ...core.logging import get_logger
from .data_models import ContextMessage
from .inspect import has_assistant_tool_call
from .operations import get_refreshed_system_message, replace_context_messages
from .queries import get_context_messages
from .transforms import is_system_instruction

logger = get_logger()


class Validator:
    def __init__(self, ctx: ElroyContext, context_messages: Iterable[ContextMessage]):
        self.ctx = ctx
        self.errors = []
        self.original_context_messages: List[ContextMessage] = list(context_messages)

    def assistant_tool_calls_followed_by_tool(self, context_messages: Iterable[ContextMessage]) -> Iterable[ContextMessage]:
        """
        Validates that any assistant message with non-empty tool_calls is followed by corresponding tool messages.
        """
        ctx_msg_list = list(context_messages)

        for idx, message in enumerate(ctx_msg_list):
            if message.role == ASSISTANT and message.tool_calls is not None:
                if idx == len(ctx_msg_list) - 1:
                    self.errors.append("Last message is assistant message with tool_calls, repairing by removing tool_calls")
                    message.tool_calls = None
                    message.id = None
                elif ctx_msg_list[idx + 1].role != TOOL:
                    self.errors.append(
                        f"Assistant message with tool_calls not followed by tool message: ID = {message.id}, repairing by removing tool_calls"
                    )
                    message.tool_calls = None
                    message.id = None
                else:
                    expected_tool_call_ids = {tc.id for tc in message.tool_calls}
                    actual_tool_calls_ids = {
                        tool_msg.tool_call_id
                        for tool_msg in ctx_msg_list[idx + 1 : idx + 1 + len(message.tool_calls)]
                        if tool_msg.role == TOOL
                    }

                    missing_tool_call_ids = expected_tool_call_ids - actual_tool_calls_ids
                    if missing_tool_call_ids:
                        self.errors.append(
                            f"Assistant message has tool_call without corresponding tool_message. tool call id(s): {missing_tool_call_ids}). Removing them."
                        )
                        message.tool_calls = [tc for tc in message.tool_calls if tc.id not in missing_tool_call_ids]
                        message.id = None
                        # we will rely on tool_messages_have_assistant_tool_call to remove any extra tool messages.
            yield message

    def tool_messages_have_assistant_tool_call(self, context_messages: Iterable[ContextMessage]) -> Iterable[ContextMessage]:
        """
        Validates that all tool messages have a preceding assistant message with the corresponding tool_calls.
        """

        ctx_msg_list = list(context_messages)

        for idx, message in enumerate(ctx_msg_list):
            if message.role == TOOL and not has_assistant_tool_call(message.tool_call_id, ctx_msg_list[:idx]):
                self.errors.append(
                    f"Tool message without preceding assistant message with tool_calls: ID = {message.id}. Repairing by removing tool message"
                )
                continue
            else:
                yield message

    def system_instruction_correctly_placed(self, context_messages: Iterable[ContextMessage]) -> Iterable[ContextMessage]:
        ctx_msg_list = list(context_messages)

        for idx, message in enumerate(ctx_msg_list):
            if idx == 0 and not is_system_instruction(message):
                self.errors.append(f"First message is not system instruction, repairing by inserting system instruction")
                yield get_refreshed_system_message(self.ctx)
                yield message
            elif idx != 0 and is_system_instruction(message):
                self.errors.append("Found system message in non-first position, repairing by dropping message")
                continue
            else:
                yield message

    def first_user_precedes_first_assistant(self, context_messages: Iterable[ContextMessage]) -> Iterable[ContextMessage]:
        first_user_msg_seen = False

        for msg in context_messages:
            if first_user_msg_seen:
                yield msg
            elif msg.role == USER:
                first_user_msg_seen = True
                yield msg
            elif msg.role == ASSISTANT:
                self.errors.append("First non-system message is not user message, repairing by inserting user message")
                yield ContextMessage(role=USER, content="The user has begun the conversation", chat_model=None)
                first_user_msg_seen = True
                yield msg
            else:
                yield msg

    def validated_msgs(self) -> Generator[ContextMessage, None, None]:
        messages: List[ContextMessage] = pipe(
            self.original_context_messages,
            self.system_instruction_correctly_placed,
            self.assistant_tool_calls_followed_by_tool,
            self.tool_messages_have_assistant_tool_call,
            self.first_user_precedes_first_assistant if self.ctx.chat_model.ensure_alternating_roles else identity,
            list,
        )  # type: ignore

        if self.errors:
            logger.info("Context messages have been repaired")
            for error in self.errors:
                logger.info(error)
            replace_context_messages(self.ctx, messages)
            yield from get_context_messages(self.ctx)
        else:
            yield from messages
