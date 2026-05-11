"""Session/workflow controller for the Textual app."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

from ..core.constants import ASSISTANT, USER
from ..core.ctx import ElroyConfig
from ..core.runtime import build_ui_runtime
from ..core.session import open_turn_context
from ..core.turn import ElroySession
from .commands import ToolCommandSpec, execute_tool_command


@dataclass(frozen=True)
class SessionBootstrapData:
    """Bootstrap data needed to initialize the TUI session."""

    context_messages: list
    bootstrap_tool_call_ids: set[str]
    should_greet: bool


class SessionController:
    """Coordinates chat, tool, and context-refresh workflows for the TUI."""

    def __init__(self, ctx: ElroyConfig, session: ElroySession):
        self.ctx = ctx
        self.session = session
        self.runtime = build_ui_runtime(ctx)

    def load_bootstrap_data(self, enable_greeting: bool) -> SessionBootstrapData:
        from ..cli.chat import get_session_context
        from ..repository.context_messages.factory import build_context_message_read_store, build_context_refresh_orchestrator
        from ..repository.context_messages.session import build_context_message_session
        from ..repository.context_messages.tools import to_synthetic_tool_call
        from ..repository.context_messages.transforms import get_time_since_most_recent_user_message
        from ..repository.context_messages.validations import Validator

        with open_turn_context(self.ctx, self.session) as turn:
            context_session = build_context_message_session(turn)
            context_refresh_orchestrator = build_context_refresh_orchestrator(context_session)
            context_refresh_orchestrator.add_context_messages(to_synthetic_tool_call("get_session_context", get_session_context(turn)))
            context_messages = list(
                Validator(turn, build_context_message_read_store(context_session).get_context_messages()).validated_msgs()
            )
        bootstrap_tool_call_ids = {
            tool_call.id
            for message in context_messages
            if message.role == ASSISTANT and message.tool_calls
            for tool_call in message.tool_calls
            if tool_call.function.get("name") == "get_session_context"
        }
        should_greet = enable_greeting and (
            (get_time_since_most_recent_user_message(context_messages) or timedelta()) >= self.runtime.min_convo_age_for_greeting
        )
        return SessionBootstrapData(
            context_messages=context_messages,
            bootstrap_tool_call_ids=bootstrap_tool_call_ids,
            should_greet=should_greet,
        )

    def greeting_stream(self) -> Iterator:
        from ..messenger.messenger import process_message

        return process_message(role=USER, ctx=self.ctx, session=self.session, msg="<Empty user response>", enable_tools=False)

    def restart_stream(self, prompt: str) -> Iterator:
        from ..messenger.messenger import process_message

        return process_message(
            role=USER,
            ctx=self.ctx,
            session=self.session,
            msg=prompt,
            enable_tools=False,
            persist_input_message=False,
        )

    def chat_stream(self, text: str) -> Iterator:
        from ..messenger.messenger import process_message

        return process_message(role=USER, ctx=self.ctx, session=self.session, msg=text)

    def run_tool_command(self, spec: ToolCommandSpec, values: dict[str, str]):
        return execute_tool_command(spec, self.ctx, self.session, values)

    def refresh_context_if_needed(self) -> None:
        from ..repository.context_messages.factory import build_context_refresh_orchestrator
        from ..repository.context_messages.session import build_context_message_session

        with open_turn_context(self.ctx, self.session) as turn:
            build_context_refresh_orchestrator(build_context_message_session(turn)).refresh_context_if_needed()
