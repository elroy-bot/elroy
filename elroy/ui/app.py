"""Textual TUI for Elroy chat interface."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import ClassVar, Literal
from urllib.parse import unquote, urlparse

from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Footer, Label, RichLog, TextArea
from textual.worker import Worker, get_current_worker

from .. import __version__
from ..core.constants import EXIT, RecoverableToolError
from ..core.ctx import ElroyConfig
from ..core.logging import get_logger
from ..core.runtime import build_command_runtime, build_ui_runtime
from ..core.session import build_elroy_session, open_turn_context
from ..core.sidebar_models import DetailModalSpec, SidebarEntry, SidebarState
from ..core.turn import ElroySession, RestartRequest
from ..io.base import ElroyIO
from ..io.formatters.rich_formatter import RichFormatter
from ..io.prompt_history import PromptHistoryStore
from ..repository.user.queries import get_assistant_name
from ..repository.user.session import build_user_runtime, build_user_session
from .command_flow import CommandFlowController
from .commands import (
    ToolCommandProvider,
    ToolCommandSpec,
)
from .conversation import ConversationController
from .forms import CommandFormScreen
from .output import TextualIO
from .session import SessionController
from .sidebar import SidebarController
from .status import StatusController
from .widgets import ConversationPane, SidebarListView, SidebarPanel, StatusBar

logger = get_logger()
RESTART_RESUME_MESSAGE_ENV = "ELROY_RESTART_RESUME_MESSAGE"


@dataclass(frozen=True)
class DetailModalResult:
    action: Literal["delete", "complete"]


@dataclass(frozen=True)
class AppRestartRequest:
    resume_prompt: str


class DetailModal(ModalScreen):
    """Shows the full content of a selected sidebar entry."""

    DEFAULT_CSS = """
    DetailModal {
        align: center middle;
    }
    #memory-detail-container {
        width: 80%;
        height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }
    #memory-detail-title {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
        text-align: center;
    }
    #memory-detail-log {
        height: 1fr;
    }
    #memory-detail-footer {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    #memory-detail-footer.confirm {
        color: $warning;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [Binding("escape,enter,q", "dismiss", "Close", show=False)]

    def __init__(
        self,
        title: str,
        content: str,
        can_delete: bool = False,
        can_complete: bool = False,
    ):
        super().__init__()
        self._memory_title = title
        self._memory_content = content
        self._can_delete = can_delete
        self._can_complete = can_complete
        self._confirming_delete = False

    def compose(self) -> ComposeResult:
        with Vertical(id="memory-detail-container"):
            yield Label(self._memory_title, id="memory-detail-title")
            yield RichLog(id="memory-detail-log", wrap=True, highlight=False, markup=False)
            yield Label(self._build_footer_text(), id="memory-detail-footer")

    def on_mount(self) -> None:
        self.query_one("#memory-detail-log", RichLog).write(self._memory_content)

    def on_key(self, event: events.Key) -> None:
        if event.key == "d" and self._can_delete:
            if self._confirming_delete:
                self.dismiss(DetailModalResult(action="delete"))
            else:
                self._confirming_delete = True
                footer = self.query_one("#memory-detail-footer", Label)
                footer.update("Press D again to confirm deletion, any other key to cancel")
                footer.add_class("confirm")
            event.stop()
        elif event.key == "c" and self._can_complete:
            self.dismiss(DetailModalResult(action="complete"))
            event.stop()
        elif self._confirming_delete:
            self._confirming_delete = False
            footer = self.query_one("#memory-detail-footer", Label)
            footer.update(self._build_footer_text())
            footer.remove_class("confirm")

    def _build_footer_text(self) -> str:
        actions: list[str] = []
        if self._can_complete:
            actions.append("C: complete")
        if self._can_delete:
            actions.append("D: delete")
        actions.append("Escape/Enter/Q: close")
        return "  |  ".join(actions)


class ChatInput(TextArea):
    """Wrapped chat composer that keeps messages single-paragraph on submit."""

    class SubmitRequested(Message):
        pass

    class HistoryPreviousRequested(Message):
        pass

    class HistoryNextRequested(Message):
        pass

    class CompletionRequested(Message):
        pass

    class CommandPaletteRequested(Message):
        pass

    class FocusMemoriesRequested(Message):
        pass

    class FocusAgendaRequested(Message):
        pass

    class BrowseToggleRequested(Message):
        pass

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "submit", "Send", show=False, priority=True),
        Binding("up", "history_previous", "Previous History", show=False, priority=True),
        Binding("down", "history_next", "Next History", show=False, priority=True),
        Binding("tab", "complete_input", "Complete", show=False, priority=True),
        Binding("ctrl+p", "command_palette", "Commands", show=False, priority=True),
        Binding("ctrl+m", "focus_memories", "Memories", priority=True),
        Binding("ctrl+a", "focus_agenda", "Agenda", priority=True),
        Binding("escape", "toggle_browse", "Browse", show=False, priority=True),
    ]

    @staticmethod
    def _normalize_paste_text(text: str) -> str:
        lines = text.splitlines()
        if not lines:
            return text
        return " ".join(line.strip() for line in lines if line.strip())

    @property
    def value(self) -> str:
        return self.text

    @value.setter
    def value(self, text: str) -> None:
        self.load_text(text)
        self.move_cursor((0, len(self.text)))

    def resize_to_content(self) -> None:
        content_height = max(1, self.virtual_size.height)
        self.styles.height = max(3, min(8, content_height + 2))

    async def _on_paste(self, event: events.Paste) -> None:
        text = self._normalize_paste_text(event.text)
        if text:
            start, end = self.selection
            result = self.replace(text, start, end)
            self.move_cursor(result.end_location)
        event.stop()

    def action_paste(self) -> None:
        clipboard = self._normalize_paste_text(self.app.clipboard)
        start, end = self.selection
        result = self.replace(clipboard, start, end)
        self.move_cursor(result.end_location)

    def action_submit(self) -> None:
        self.post_message(self.SubmitRequested())

    def action_history_previous(self) -> None:
        self.post_message(self.HistoryPreviousRequested())

    def action_history_next(self) -> None:
        self.post_message(self.HistoryNextRequested())

    def action_complete_input(self) -> None:
        self.post_message(self.CompletionRequested())

    def action_command_palette(self) -> None:
        self.post_message(self.CommandPaletteRequested())

    def action_focus_memories(self) -> None:
        self.post_message(self.FocusMemoriesRequested())

    def action_focus_agenda(self) -> None:
        self.post_message(self.FocusAgendaRequested())

    def action_toggle_browse(self) -> None:
        self.post_message(self.BrowseToggleRequested())


class ElroyApp(App):
    """Main Textual TUI application for Elroy."""

    COMMANDS = App.COMMANDS | {ToolCommandProvider}
    DARK = True  # Force dark theme regardless of terminal preference
    SIDEBAR_SECTIONS: ClassVar[tuple[str, ...]] = ("memories", "agenda", "improvements", "feature_requests", "codex_sessions")
    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }

    #conversation-container {
        height: 1fr;
        layout: horizontal;
    }

    #left-panel {
        height: 1fr;
        layout: vertical;
        width: 1fr;
        border-right: solid $surface;
    }

    #left-panel.active {
        border-right: solid $primary;
    }

    #history-log {
        height: 1fr;
        border: none;
        background: $surface;
        scrollbar-background: $surface;
        scrollbar-color: $primary;
        scrollbar-background-hover: $surface;
        scrollbar-color-hover: $primary-lighten-1;
        scrollbar-background-active: $surface;
        scrollbar-color-active: $primary-lighten-2;
    }

    #memory-panel {
        width: 36;
        height: 1fr;
        border-left: solid $primary;
    }

    #sidebar-tabs {
        dock: top;
    }

    #sidebar-switcher {
        height: 1fr;
    }

    .panel-list {
        height: 1fr;
        margin: 0;
        border: none;
    }

    .panel-list > ListItem.-hovered {
        background: $surface-lighten-1;
        color: $text;
    }

    .panel-list > ListItem.-highlight {
        background: $primary-darken-1;
        color: $text;
    }

    .panel-list:focus > ListItem.-highlight {
        background: $primary;
        color: $text;
    }

    #chat-input {
        min-height: 3;
        max-height: 8;
        border: round $primary;
    }

    #status-bar {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+d", "quit", "Exit", priority=True),
        Binding("ctrl+c", "cancel_stream", "Cancel Stream", show=False),
        Binding("ctrl+m", "focus_memories", "Memories"),
        Binding("ctrl+a", "focus_agenda", "Agenda"),
        Binding("m", "focus_memories", "Memories", show=False),
        Binding("g", "focus_agenda", "Agenda", show=False),
    ]

    def __init__(
        self,
        ctx: ElroyConfig,
        session: ElroySession,
        formatter: RichFormatter,
        enable_greeting: bool,
        show_internal_thought: bool,
        restart_resume_message: str | None = None,
    ):
        super().__init__()
        self.ctx = ctx
        self.session = session
        self.session.restart_state.enable()
        self.runtime = build_ui_runtime(ctx)
        self.formatter = formatter
        self.enable_greeting = enable_greeting
        self.restart_resume_message = restart_resume_message
        self.prompt_history = PromptHistoryStore()
        self.conversation_controller = ConversationController(formatter, self.prompt_history, show_internal_thought)
        self.io: ElroyIO = TextualIO(self, formatter, show_internal_thought)
        self.command_flow = CommandFlowController(build_command_runtime(ctx))
        self.sidebar_controller = SidebarController(ctx, session)
        self.session_controller = SessionController(ctx, session)
        self._panel_entries: dict[str, list[SidebarEntry]] = {buffer_name: [] for buffer_name in self.SIDEBAR_SECTIONS}
        self._sidebar_indices: dict[str, int | None] = dict.fromkeys(self.SIDEBAR_SECTIONS)
        self._last_non_chat_target: Literal["sidebar", "history"] = "sidebar"
        self._history_index = -1
        self._spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.status_controller = StatusController(self._spinner_chars)
        self._spinner_handle = None
        self._bg_status_handle = None
        self._chat_suggestions: list[str] = []
        self._context_poll_handle = None
        self._rendered_context_message_ids: set[int] = set()
        self._context_poll_ready = False

    @property
    def _browse_mode(self) -> bool:
        return not self._chat_input().has_focus

    @property
    def _browse_target(self) -> str:
        if self._conversation_pane().history_has_focus():
            return "history"
        return "sidebar"

    @property
    def _active_worker_groups(self) -> set[str]:
        return self.status_controller.active_groups

    @property
    def chat_suggestions(self) -> list[str]:
        return self._chat_suggestions

    @property
    def tool_command_specs(self) -> list[ToolCommandSpec]:
        return self.command_flow.tool_command_specs

    def get_system_commands(self, screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand("Focus Memories", "Switch the sidebar to memories", self.action_focus_memories)
        yield SystemCommand("Focus Agenda", "Switch the sidebar to agenda", self.action_focus_agenda)
        yield SystemCommand(
            "Refresh System Instructions",
            "Rebuild the system instructions for the current conversation",
            lambda: self.launch_tool_command("refresh_system_instructions"),
        )
        yield SystemCommand("Reset Messages", "Clear the current conversation", lambda: self.launch_tool_command("reset_messages"))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        _ = parameters
        if action == "cancel_stream":
            return "chat-stream" in self.status_controller.active_groups
        return None

    # ── history ──────────────────────────────────────────────────────────────

    def _remember_prompt(self, text: str) -> None:
        self.conversation_controller.remember_prompt(text)

    # ── layout ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(id="conversation-container"):
            yield ConversationPane(id="left-panel")
            yield SidebarPanel(id="memory-panel")
        yield ChatInput(placeholder="> ", id="chat-input")
        yield StatusBar("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._chat_input().focus()
        self.call_after_refresh(self._resize_chat_input)

        with open_turn_context(self.ctx, self.session) as turn:
            self.title = get_assistant_name(build_user_session(turn), build_user_runtime(turn))
        self._render_status_bar()
        self._bg_status_handle = self.set_interval(1.0, self._tick_background_status)
        self._start_session()

    # ── commands ─────────────────────────────────────────────────────────────

    def get_tool_command_spec(self, name: str) -> ToolCommandSpec | None:
        return self.command_flow.get_tool_command_spec(name)

    def launch_tool_command(self, name: str, initial_values: dict[str, str] | None = None, source: str = "palette") -> None:
        request = self.command_flow.resolve_launch_request(name, initial_values=initial_values, source=source)
        if request is None:
            self._emit_error(f"Invalid command: {name}")
            return
        if request.execute_immediately:
            self._execute_tool_command(request.spec.name, request.initial_values, request.source)
            return
        self.push_screen(
            CommandFormScreen(request.spec, request.initial_values),
            lambda values, spec_name=request.spec.name, source_name=request.source: self._handle_command_form_result(
                spec_name, source_name, values
            ),
        )

    def _handle_command_form_result(self, name: str, source: str, values: dict[str, str] | None) -> None:
        if values is None:
            return
        self._execute_tool_command(name, values, source)

    @work(thread=True, group="command-action", exclusive=True, exit_on_error=False)
    def _execute_tool_command(self, name: str, values: dict[str, str], source: str) -> None:
        spec = self.get_tool_command_spec(name)
        if spec is None:
            self.call_from_thread(self._emit_error, f"Invalid command: {name}")
            return

        logger.debug("Starting tool command execution: name=%s source=%s values=%s", name, source, values)
        self.call_from_thread(self._set_status_message, f"running {spec.name}")
        try:
            result = self.session_controller.run_tool_command(spec, values)
            logger.debug("Tool command completed: name=%s result_type=%s", name, type(result).__name__)
            if isinstance(result, Iterator):
                self._run_stream(result)
            elif result is not None:
                self.call_from_thread(self._display_command_result, result, spec, source)
        except RecoverableToolError as exc:
            logger.debug("Recoverable tool error during command execution: name=%s error=%s", name, exc)
            self.call_from_thread(self._emit_error, str(exc))
        except Exception:
            logger.exception("Unexpected error during tool command execution: name=%s", name)
            raise
        finally:
            logger.debug("Scheduling post-command UI finalization: name=%s", name)
            self.call_from_thread(self._refresh_sidebar_state)
            self.call_from_thread(self._finalize_turn_ui_state)

    def _display_command_result(self, result, spec: ToolCommandSpec, source: str) -> None:
        self.conversation_controller.display_command_result(self._conversation_pane(), self.notify, result, spec, source)

    # ── memory panel ─────────────────────────────────────────────────────────

    def on_sidebar_panel_entry_selected(self, message: SidebarPanel.EntrySelected) -> None:
        self._remember_sidebar_selection(message.section, message.index)
        self._last_non_chat_target = "sidebar"
        self._open_panel_entry(message.section, message.index)
        self._render_focus_state()

    def on_sidebar_panel_entry_highlighted(self, message: SidebarPanel.EntryHighlighted) -> None:
        self._remember_sidebar_selection(message.section, message.index)
        self._last_non_chat_target = "sidebar"
        self._render_focus_state()

    def on_sidebar_panel_section_changed(self, message: SidebarPanel.SectionChanged) -> None:
        self._apply_sidebar_selection(message.section)
        if self._sidebar_has_focus():
            self._sidebar_panel().focus_current_list()
        self._last_non_chat_target = "sidebar"
        self._render_focus_state()

    def on_chat_input_submit_requested(self, _: ChatInput.SubmitRequested) -> None:
        self._submit_chat_input()

    def on_chat_input_history_previous_requested(self, _: ChatInput.HistoryPreviousRequested) -> None:
        input_widget = self._chat_input()
        if self.conversation_controller.input_history and self._history_index < len(self.conversation_controller.input_history) - 1:
            self._history_index += 1
            input_widget.value = self.conversation_controller.input_history[self._history_index]

    def on_chat_input_history_next_requested(self, _: ChatInput.HistoryNextRequested) -> None:
        input_widget = self._chat_input()
        if self._history_index > 0:
            self._history_index -= 1
            input_widget.value = self.conversation_controller.input_history[self._history_index]
        elif self._history_index == 0:
            self._history_index = -1
            input_widget.value = ""

    def on_chat_input_completion_requested(self, _: ChatInput.CompletionRequested) -> None:
        self._accept_input_completion()

    def on_chat_input_command_palette_requested(self, _: ChatInput.CommandPaletteRequested) -> None:
        self.action_command_palette()

    def on_chat_input_focus_memories_requested(self, _: ChatInput.FocusMemoriesRequested) -> None:
        self.action_focus_memories()

    def on_chat_input_focus_agenda_requested(self, _: ChatInput.FocusAgendaRequested) -> None:
        self.action_focus_agenda()

    def on_chat_input_browse_toggle_requested(self, _: ChatInput.BrowseToggleRequested) -> None:
        self.action_toggle_browse()

    # ── session init ─────────────────────────────────────────────────────────

    @work(thread=True, group="session-bootstrap", exclusive=True, exit_on_error=False)
    def _start_session(self) -> None:
        bootstrap_data = self.session_controller.load_bootstrap_data(self.enable_greeting)
        sidebar_state = self.sidebar_controller.build_state()
        before_ids = {message.id for message in bootstrap_data.context_messages if message.id is not None}
        self.call_from_thread(
            self._render_existing_context_messages,
            bootstrap_data.context_messages,
            bootstrap_data.bootstrap_tool_call_ids,
        )
        self.call_from_thread(self._mark_context_messages_rendered, bootstrap_data.context_messages)
        self.call_from_thread(self._apply_sidebar_state, sidebar_state)

        if self.restart_resume_message:
            self._run_stream(self.session_controller.restart_stream(self.restart_resume_message))
            self.call_from_thread(self._mark_messages_rendered_after_bootstrap_stream, before_ids)
        elif bootstrap_data.should_greet:
            self._run_stream(self.session_controller.greeting_stream())
            self.call_from_thread(self._mark_messages_rendered_after_bootstrap_stream, before_ids)
        self.call_from_thread(self._start_context_polling)

    # ── streaming helpers ─────────────────────────────────────────────────────

    def _run_stream(self, stream: Iterator) -> None:
        """Consume a message stream from a worker thread."""
        from ..llm.stream_parser import StatusUpdate

        worker = get_current_worker()
        self.call_from_thread(self._start_spinner)
        try:
            for item in stream:
                if worker.is_cancelled:
                    break
                if isinstance(item, StatusUpdate):
                    self.call_from_thread(self._set_status_message, item.content)
                else:
                    self.io.print(item, end="")
        finally:
            self.call_from_thread(self._flush_thought_buffer)
            self.call_from_thread(self._flush_streaming_buffer)
            self.call_from_thread(self._stop_spinner)

    def _append_streaming_token(self, token: str, style: str) -> None:
        self.conversation_controller.append_streaming_token(self._conversation_pane(), token, style)

    def _flush_streaming_buffer(self) -> None:
        self.conversation_controller.flush_streaming_buffer(self._conversation_pane())

    def _append_thought_token(self, token: str) -> None:
        self.conversation_controller.append_thought_token(token)

    def _flush_thought_buffer(self) -> None:
        self.conversation_controller.flush_thought_buffer(self._conversation_pane())

    def _write_to_history(self, renderable) -> None:
        self.conversation_controller.write_to_history(self._conversation_pane(), renderable)

    def _render_existing_context_messages(self, context_messages: list, bootstrap_tool_call_ids: set[str]) -> None:
        self.conversation_controller.render_existing_context_messages(
            self._conversation_pane(),
            context_messages,
            bootstrap_tool_call_ids,
        )

    def _mark_context_messages_rendered(self, context_messages: list) -> None:
        self._rendered_context_message_ids.update(message.id for message in context_messages if message.id is not None)

    def _render_new_context_messages(self, unseen_messages: list) -> None:
        self.conversation_controller.render_existing_context_messages(
            self._conversation_pane(),
            unseen_messages,
            set(),
        )
        self._mark_context_messages_rendered(unseen_messages)

    def _start_context_polling(self) -> None:
        if self._context_poll_handle is None:
            self._context_poll_handle = self.set_interval(1.0, self._kick_context_update_poll)
        self._context_poll_ready = True

    def _mark_messages_rendered_after_bootstrap_stream(self, before_ids: set[int]) -> None:
        self._mark_trailing_context_messages_rendered(before_ids=before_ids)

    def _mark_messages_rendered_after_chat_turn(self, text: str, before_ids: set[int]) -> None:
        self._mark_trailing_context_messages_rendered(before_ids=before_ids, anchor_role="user", anchor_content=text)

    def _mark_trailing_context_messages_rendered(
        self,
        *,
        before_ids: set[int],
        anchor_role: str | None = None,
        anchor_content: str | None = None,
    ) -> None:
        context_messages = self.session_controller.load_context_messages()
        new_messages = [message for message in context_messages if message.id is not None and message.id not in before_ids]
        if not new_messages:
            return
        start_index = 0
        if anchor_role is not None:
            start_index = next(
                (
                    index
                    for index in range(len(new_messages) - 1, -1, -1)
                    if new_messages[index].role == anchor_role and new_messages[index].content == anchor_content
                ),
                -1,
            )
            if start_index < 0:
                return
        self._mark_context_messages_rendered(new_messages[start_index:])

    # ── input handling ────────────────────────────────────────────────────────

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "chat-input":
            self.call_after_refresh(self._resize_chat_input)

    def _submit_chat_input(self) -> None:
        text = self._chat_input().value.strip()
        if not text:
            return
        if self._submit_blocked():
            self._emit_error("Wait for the current task to finish before sending another message.")
            return

        self._chat_input().value = ""
        self._resize_chat_input()

        self._remember_prompt(text)
        self._history_index = -1
        if text.lower() in (EXIT, f"/{EXIT}"):
            self.exit()
            return

        self._write_to_history(Text(f"\nYou: {text}", style=self.formatter.user_input_color))
        self._process_chat_message(text)

    def _submit_blocked(self) -> bool:
        return self.status_controller.is_submit_blocked()

    def on_key(self, event: events.Key) -> None:
        input_widget = self._chat_input()
        if self.screen is not self.screen_stack[0]:
            return

        if self._handle_global_key(event, input_widget):
            return
        if self._recover_focus_if_needed():
            self._consume_key(event)
            return
        if input_widget.has_focus:
            return
        if self._handle_non_chat_key(event):
            return

    @work(thread=True, group="chat-stream", exclusive=True, exit_on_error=False)
    def _process_chat_message(self, text: str) -> None:
        self.call_from_thread(self._set_status_message, "thinking...")
        before_ids = {message.id for message in self.session_controller.load_context_messages() if message.id is not None}
        try:
            self._run_stream(self.session_controller.chat_stream(text))
            self.call_from_thread(self._mark_messages_rendered_after_chat_turn, text, before_ids)
        except Exception as exc:
            self.call_from_thread(self._emit_error, str(exc))
            logger.exception("Error processing chat input")
        finally:
            self.call_from_thread(self._refresh_sidebar_state)
            self.call_from_thread(self._finalize_turn_ui_state)

    # ── actions ───────────────────────────────────────────────────────────────

    def action_cancel_stream(self) -> None:
        if "chat-stream" in self._active_worker_groups:
            self.workers.cancel_group(self, "chat-stream")
            self._flush_streaming_buffer()
            with open_turn_context(self.ctx, self.session) as turn:
                build_user_session(turn).db.rollback()

    def action_toggle_browse(self) -> None:
        if self._chat_input().has_focus:
            if self._last_non_chat_target == "history":
                self._focus_history()
            else:
                self._focus_sidebar()
            return
        self._focus_chat_input()

    def action_toggle_memory(self) -> None:
        self.action_focus_memories()

    def action_focus_memories(self) -> None:
        self._switch_sidebar_section("memories", focus_sidebar=True)

    def action_focus_agenda(self) -> None:
        self._switch_sidebar_section("agenda", focus_sidebar=True)

    # ── sidebar workers ──────────────────────────────────────────────────────

    def _refresh_sidebar_state(self) -> None:
        self._fetch_sidebar_state()

    @work(thread=True, group="sidebar-refresh", exclusive=True, exit_on_error=False)
    def _fetch_sidebar_state(self) -> None:
        try:
            state = self.sidebar_controller.build_state()
            self.call_from_thread(self._apply_sidebar_state, state)
        except Exception:
            logger.debug("Failed to refresh sidebar state", exc_info=True)

    def _apply_sidebar_state(self, state: SidebarState) -> None:
        self._panel_entries = {
            "memories": state.memories,
            "agenda": state.agenda,
            "improvements": state.improvements,
            "feature_requests": state.feature_requests,
            "codex_sessions": state.codex_sessions,
        }
        self._chat_suggestions = state.completions
        self._render_sidebar_lists()
        if self._sidebar_has_focus():
            self.call_after_refresh(self._apply_sidebar_selection, self.current_sidebar_section)

    @work(thread=True, group="deferred-context-refresh", exclusive=True, exit_on_error=False)
    def _deferred_context_refresh(self) -> None:
        try:
            self.session_controller.refresh_context_if_needed()
        except Exception:
            logger.debug("Deferred context refresh failed", exc_info=True)

    def _schedule_context_refresh(self) -> None:
        self.set_timer(5.0, self._deferred_context_refresh)

    def _kick_context_update_poll(self) -> None:
        if not self._context_poll_ready:
            return
        self._poll_context_updates()

    @work(thread=True, group="background-context-poll", exclusive=True, exit_on_error=False)
    def _poll_context_updates(self) -> None:
        try:
            context_messages = self.session_controller.load_context_messages()
            unseen_indices = [
                index for index, message in enumerate(context_messages) if message.id not in self._rendered_context_message_ids
            ]
            if not unseen_indices:
                return
            first_unseen = unseen_indices[0]
            if any(message.id in self._rendered_context_message_ids for message in context_messages[first_unseen + 1 :]):
                self.call_from_thread(self._mark_context_messages_rendered, context_messages)
                return
            unseen_messages = [message for message in context_messages[first_unseen:] if message.id is not None]
            if unseen_messages:
                self.call_from_thread(self._render_new_context_messages, unseen_messages)
        except Exception:
            logger.debug("Background context update poll failed", exc_info=True)

    def _finalize_turn_ui_state(self) -> None:
        logger.debug("Finalizing turn UI state")
        try:
            restart_request = self.session.restart_state.consume()
            if restart_request is not None:
                logger.info("Pending restart request found during UI finalization")
                self._restart_app(restart_request)
                return
            logger.debug("No pending restart request during UI finalization; scheduling context refresh")
            self._schedule_context_refresh()
        except Exception:
            logger.exception("Failed while finalizing turn UI state")
            raise

    def _restart_app(self, restart_request: RestartRequest) -> None:
        logger.info("Restarting Elroy app with resume_prompt=%r", restart_request.resume_prompt)
        self.notify("Restarting Elroy...")
        self.exit(result=AppRestartRequest(resume_prompt=restart_request.resume_prompt))

    # ── worker state / status ────────────────────────────────────────────────

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        group = getattr(event.worker, "group", "default")
        if not self.status_controller.should_track_group(group):
            return
        transition = self.status_controller.handle_worker_state_changed(
            group,
            event.state,
            str(event.worker.error) if event.worker.error else None,
        )
        if transition.status_message is not None:
            self.status_controller.set_status_message(transition.status_message)
        if transition.error_message is not None:
            self._emit_error(transition.error_message)
        elif transition.notify_cancelled:
            self.notify("Chat stream cancelled")
        if transition.should_render:
            self._render_status_bar()

    def _start_spinner(self) -> None:
        self.status_controller.reset_spinner()
        if self._spinner_handle:
            self._spinner_handle.stop()
        self._spinner_handle = self.set_interval(0.08, self._tick_spinner)

    def _tick_spinner(self) -> None:
        self.status_controller.advance_spinner()
        self._render_status_bar()

    def _set_status_message(self, message: str) -> None:
        self.status_controller.set_status_message(message)
        self._render_status_bar()

    def _stop_spinner(self) -> None:
        if self._spinner_handle:
            self._spinner_handle.stop()
            self._spinner_handle = None
        self._render_status_bar()

    def _tick_background_status(self) -> None:
        if self.status_controller.should_render_background_status():
            self._render_status_bar()

    def _emit_error(self, message: str) -> None:
        self.notify(message, severity="error")
        self._write_to_history(Text(f"Error: {message}", style=self.formatter.warning_color))

    # ── focus / navigation helpers ──────────────────────────────────────────

    @property
    def current_sidebar_section(self) -> str:
        return self._sidebar_panel().current_section

    def _focus_chat_input(self) -> None:
        self._chat_input().focus()
        self._render_focus_state()

    def _resize_chat_input(self) -> None:
        self._chat_input().resize_to_content()

    def _focus_sidebar(self) -> None:
        self._sidebar_panel().focus_current_list()
        self._apply_sidebar_selection(self.current_sidebar_section)
        self._last_non_chat_target = "sidebar"
        self._render_focus_state()

    def _focus_history(self) -> None:
        self._conversation_pane().focus_history()
        self._last_non_chat_target = "history"
        self._render_focus_state()

    def _cycle_non_chat_focus(self) -> None:
        if self._history_has_focus():
            self._focus_sidebar()
            return
        self._focus_history()

    def _render_sidebar_lists(self) -> None:
        selected_indices = {section: self._resolved_sidebar_index(section) for section in self.SIDEBAR_SECTIONS}
        self._sidebar_panel().render_entries(self._panel_entries, selected_indices)
        self._render_focus_state()

    def _resolved_sidebar_index(self, section: str) -> int | None:
        entries = self._panel_entries[section]
        if not entries:
            self._sidebar_indices[section] = None
            return None
        saved_index = self._sidebar_indices[section]
        if saved_index is None:
            saved_index = 0
        saved_index = max(0, min(saved_index, len(entries) - 1))
        self._sidebar_indices[section] = saved_index
        return saved_index

    def _apply_sidebar_selection(self, section: str) -> None:
        self._sidebar_panel().apply_selection(section, self._resolved_sidebar_index(section))

    def _switch_sidebar_section(self, section: str, focus_sidebar: bool = False) -> None:
        if section not in self._panel_entries:
            return
        self._sidebar_panel().switch_section(section)
        self._apply_sidebar_selection(section)
        if focus_sidebar or self._sidebar_has_focus():
            self._sidebar_panel().focus_current_list()
            self._last_non_chat_target = "sidebar"
            self._sidebar_panel().call_after_refresh(self._apply_sidebar_selection, section)
        self._render_focus_state()

    def _open_panel_entry(self, section: str, index: int) -> None:
        entries = self._panel_entries[section]
        if not (0 <= index < len(entries)):
            return

        entry = entries[index]
        modal = self.sidebar_controller.build_detail_modal(entry)
        if modal is None:
            return

        self.push_screen(
            DetailModal(
                modal.title,
                modal.content,
                can_delete=modal.can_delete,
                can_complete=modal.can_complete,
            ),
            lambda result, modal_spec=modal: self._handle_detail_modal_result(modal_spec, result),
        )

    def _handle_detail_modal_result(self, modal: DetailModalSpec, result: DetailModalResult | None) -> None:
        if result is None:
            return
        if self.sidebar_controller.apply_modal_result(modal, result.action):
            self._refresh_sidebar_state()

    def _accept_input_completion(self) -> None:
        self.conversation_controller.accept_input_completion(self._chat_input(), self._chat_suggestions)

    def _remember_sidebar_selection(self, section: str, index: int | None) -> None:
        self._sidebar_indices[section] = index

    def _consume_key(self, event: events.Key) -> None:
        event.prevent_default()
        event.stop()

    def _handle_global_key(self, event: events.Key, input_widget: ChatInput) -> bool:
        if event.key == "ctrl+c" and input_widget.has_focus and input_widget.value:
            input_widget.value = ""
            self._resize_chat_input()
            self._consume_key(event)
            return True

        actions = {
            "ctrl+d": self.exit,
            "ctrl+c": self.action_cancel_stream,
            "ctrl+m": self.action_focus_memories,
            "ctrl+a": self.action_focus_agenda,
        }
        action = actions.get(event.key)
        if action is None:
            return False
        action()
        self._consume_key(event)
        return True

    def _handle_non_chat_key(self, event: events.Key) -> bool:
        if event.key in {"escape", "i", "a"}:
            self._focus_chat_input()
            self._consume_key(event)
            return True
        if event.key in {"tab", "shift+tab"}:
            self._cycle_non_chat_focus()
            self._consume_key(event)
            return True
        if self._handle_sidebar_switch_key(event.key):
            self._consume_key(event)
            return True
        if self._handle_history_navigation_key(event.key):
            self._consume_key(event)
            return True
        if self._handle_sidebar_navigation_key(event.key):
            self._consume_key(event)
            return True
        return False

    def _handle_sidebar_switch_key(self, key: str) -> bool:
        section_keys = {
            "m": "memories",
            "g": "agenda",
            "r": "improvements",
            "f": "feature_requests",
            "s": "codex_sessions",
        }
        if key in section_keys:
            self._switch_sidebar_section(section_keys[key], focus_sidebar=True)
            return True
        if self._sidebar_has_focus() and key in {"left", "right"}:
            self._switch_sidebar_section(self._adjacent_sidebar_section(-1 if key == "left" else 1), focus_sidebar=True)
            return True
        return False

    def _handle_history_navigation_key(self, key: str) -> bool:
        if not self._history_has_focus() or key not in {"j", "k", "up", "down"}:
            return False
        history_log = self.query_one("#history-log", RichLog)
        if key in {"j", "down"}:
            history_log.action_scroll_down()
        else:
            history_log.action_scroll_up()
        return True

    def _handle_sidebar_navigation_key(self, key: str) -> bool:
        if not self._sidebar_has_focus() or key not in {"j", "k"}:
            return False
        list_view = self._current_sidebar_list()
        if key == "j":
            list_view.action_cursor_down()
        else:
            list_view.action_cursor_up()
        return True

    def _history_has_focus(self) -> bool:
        return self._conversation_pane().history_has_focus()

    def _sidebar_has_focus(self) -> bool:
        return any(list_view.has_focus for list_view in self._sidebar_panel().sidebar_lists())

    def _recover_focus_if_needed(self) -> bool:
        if self._chat_input().has_focus or self._history_has_focus() or self._sidebar_has_focus():
            return False
        self._focus_chat_input()
        return True

    def _adjacent_sidebar_section(self, delta: int) -> str:
        try:
            index = self.SIDEBAR_SECTIONS.index(self.current_sidebar_section)
        except ValueError:
            index = 0
        return self.SIDEBAR_SECTIONS[(index + delta) % len(self.SIDEBAR_SECTIONS)]

    def _render_focus_state(self) -> None:
        self._conversation_pane().set_history_active(self._history_has_focus())
        active_sidebar_section = self.current_sidebar_section if self._sidebar_has_focus() else None
        self._sidebar_panel().set_browse_active(active_sidebar_section)
        self._render_status_bar()

    def _render_status_bar(self) -> None:
        try:
            self.query_one("#status-bar", StatusBar).status_text = self._build_status_text()
        except Exception:
            logger.debug("Failed to render status bar", exc_info=True)

    def _build_status_text(self) -> str:
        from ..core.status import get_background_status

        bg = get_background_status()
        return self.status_controller.status_text(self.runtime.chat_model_name, bg)

    def _current_sidebar_list(self) -> SidebarListView:
        return self._sidebar_panel().current_list_view()

    def _sidebar_panel(self) -> SidebarPanel:
        return self.query_one("#memory-panel", SidebarPanel)

    def _conversation_pane(self) -> ConversationPane:
        return self.query_one("#left-panel", ConversationPane)

    def _chat_input(self) -> ChatInput:
        return self.query_one("#chat-input", ChatInput)


def make_app(**overrides) -> ElroyApp:
    """Create an ElroyApp from resolved config/env, with optional overrides."""
    from ..cli.options import get_resolved_params

    params = get_resolved_params(**overrides)
    ctx = ElroyConfig.init(use_background_threads=True, **params)
    formatter = RichFormatter(
        system_message_color=params["system_message_color"],
        assistant_message_color=params["assistant_color"],
        user_input_color=params["user_input_color"],
        warning_color=params["warning_color"],
        internal_thought_color=params["internal_thought_color"],
    )
    return ElroyApp(
        ctx=ctx,
        session=build_elroy_session(ctx),
        formatter=formatter,
        enable_greeting=params.get("enable_assistant_greeting", False),
        show_internal_thought=params.get("show_internal_thought", False),
        restart_resume_message=os.environ.get(RESTART_RESUME_MESSAGE_ENV),
    )


def _handle_cli_command(argv: list[str]) -> bool:
    if not argv:
        return False

    if argv[0] in {"version", "--version", "-V"}:
        print(__version__)
        return True

    return False


def _is_running_from_source_tree() -> bool:
    current_file = Path(__file__).resolve()
    return any((parent / "pyproject.toml").is_file() for parent in current_file.parents)


def _source_tree_root() -> Path | None:
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return None


def _editable_install_root() -> Path | None:
    try:
        direct_url_text = distribution("elroy").read_text("direct_url.json")
    except PackageNotFoundError:
        return None

    if not direct_url_text:
        return None

    try:
        direct_url = json.loads(direct_url_text)
    except json.JSONDecodeError:
        logger.warning("Unable to parse elroy direct_url metadata when building restart argv")
        return None

    if not direct_url.get("dir_info", {}).get("editable"):
        return None

    parsed_url = urlparse(direct_url.get("url", ""))
    if parsed_url.scheme != "file":
        return None

    return Path(unquote(parsed_url.path))


def _is_editable_install() -> bool:
    return _editable_install_root() is not None


def _should_restart_as_module() -> bool:
    return _is_running_from_source_tree() or _is_editable_install()


def _build_restart_argv() -> list[str]:
    orig_argv = list(getattr(sys, "orig_argv", []))
    if _should_restart_as_module():
        return [sys.executable, "-m", "elroy", *sys.argv[1:]]

    return orig_argv or [sys.executable, *sys.argv]


def _build_restart_env(resume_prompt: str) -> dict[str, str]:
    restart_env = os.environ.copy()
    restart_env[RESTART_RESUME_MESSAGE_ENV] = resume_prompt
    restart_root = _source_tree_root() or _editable_install_root()
    if restart_root is None:
        return restart_env

    root_text = str(restart_root)
    existing_pythonpath = restart_env.get("PYTHONPATH", "")
    pythonpath_entries = [entry for entry in existing_pythonpath.split(os.pathsep) if entry]
    if root_text not in pythonpath_entries:
        restart_env["PYTHONPATH"] = os.pathsep.join([root_text, *pythonpath_entries])
    return restart_env


def main(argv: list[str] | None = None) -> None:
    from ..cli.options import get_resolved_params
    from ..core.logging import setup_file_logging
    from ..core.session import init_elroy_session

    if _handle_cli_command(list(sys.argv[1:] if argv is None else argv)):
        return

    setup_file_logging()
    params = get_resolved_params()
    restart_resume_message = os.environ.pop(RESTART_RESUME_MESSAGE_ENV, None)
    ctx = ElroyConfig.init(use_background_threads=True, **params)
    formatter = RichFormatter(
        system_message_color=params["system_message_color"],
        assistant_message_color=params["assistant_color"],
        user_input_color=params["user_input_color"],
        warning_color=params["warning_color"],
        internal_thought_color=params["internal_thought_color"],
    )
    with init_elroy_session(ctx, None, check_db_migration=True, should_onboard_interactive=False) as session:
        app = ElroyApp(
            ctx=ctx,
            session=session,
            formatter=formatter,
            enable_greeting=params.get("enable_assistant_greeting", False),
            show_internal_thought=params.get("show_internal_thought", False),
            restart_resume_message=restart_resume_message,
        )
        result = app.run()
        if isinstance(result, AppRestartRequest):
            restart_argv = _build_restart_argv()
            restart_env = _build_restart_env(result.resume_prompt)
            logger.info("App exited with restart request; re-executing process")
            logger.debug("Restart argv=%s", restart_argv)
            try:
                os.execvpe(restart_argv[0], restart_argv, restart_env)
            except Exception:
                logger.exception("Failed to re-execute Elroy process for restart")
                raise


if __name__ == "__main__":
    main()
