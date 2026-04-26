"""Session/workflow controller for the Textual app."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

from ..core.constants import ASSISTANT, USER
from ..core.ctx import ElroyContext
from .commands import ToolCommandSpec, execute_tool_command


@dataclass(frozen=True)
class SessionBootstrapData:
    """Bootstrap data needed to initialize the TUI session."""

    context_messages: list
    bootstrap_tool_call_ids: set[str]
    should_greet: bool


class SessionController:
    """Coordinates chat, tool, and context-refresh workflows for the TUI."""

    def __init__(self, ctx: ElroyContext):
        self.ctx = ctx

    def load_bootstrap_data(self, enable_greeting: bool) -> SessionBootstrapData:
        from ..cli.chat import get_session_context
        from ..repository.context_messages.factory import build_context_message_read_store, build_context_refresh_orchestrator
        from ..repository.context_messages.tools import to_synthetic_tool_call
        from ..repository.context_messages.transforms import get_time_since_most_recent_user_message
        from ..repository.context_messages.validations import Validator

        context_refresh_orchestrator = build_context_refresh_orchestrator(self.ctx)
        context_refresh_orchestrator.add_context_messages(to_synthetic_tool_call("get_session_context", get_session_context(self.ctx)))
        context_messages = list(Validator(self.ctx, build_context_message_read_store(self.ctx).get_context_messages()).validated_msgs())
        bootstrap_tool_call_ids = {
            tool_call.id
            for message in context_messages
            if message.role == ASSISTANT and message.tool_calls
            for tool_call in message.tool_calls
            if tool_call.function.get("name") == "get_session_context"
        }
        should_greet = enable_greeting and (
            (get_time_since_most_recent_user_message(context_messages) or timedelta()) >= self.ctx.min_convo_age_for_greeting
        )
        return SessionBootstrapData(
            context_messages=context_messages,
            bootstrap_tool_call_ids=bootstrap_tool_call_ids,
            should_greet=should_greet,
        )

    def greeting_stream(self) -> Iterator:
        from ..messenger.messenger import process_message

        return process_message(role=USER, ctx=self.ctx, msg="<Empty user response>", enable_tools=False)

    def chat_stream(self, text: str) -> Iterator:
        from ..messenger.messenger import process_message

        return process_message(role=USER, ctx=self.ctx, msg=text)

    def run_tool_command(self, spec: ToolCommandSpec, values: dict[str, str]):
        return execute_tool_command(spec, self.ctx, values)

    def refresh_context_if_needed(self) -> None:
        from ..repository.context_messages.factory import build_context_refresh_orchestrator

        build_context_refresh_orchestrator(self.ctx).refresh_context_if_needed()
