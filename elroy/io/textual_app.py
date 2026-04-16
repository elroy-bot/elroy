"""Textual TUI for Elroy chat interface."""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Iterable, Iterator
from datetime import timedelta
from pathlib import Path
from typing import ClassVar, cast

from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import ContentSwitcher, Footer, Label, ListItem, ListView, RichLog, Static, Tab, Tabs, TextArea
from textual.worker import Worker, WorkerState, get_current_worker

from .. import __version__
from ..config.paths import get_prompt_history_path
from ..core.constants import ASSISTANT, EXIT, SYSTEM, TOOL, USER, RecoverableToolError
from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..core.services.sidebar_service import AgendaPresenter, ModalSpec, SidebarEntry, SidebarState
from ..io.base import ElroyIO
from ..io.formatters.rich_formatter import RichFormatter
from ..io.textual_commands import (
    ToolCommandProvider,
    ToolCommandSpec,
    build_initial_values,
    build_tool_command_specs,
    can_execute_from_values,
    execute_tool_command,
    parse_slash_command,
)
from ..io.textual_forms import CommandFormScreen
from ..io.textual_io import TextualIO

logger = get_logger()


class MemoryDetailModal(ModalScreen):
    """Shows the full content of a single in-context memory."""

    DEFAULT_CSS = """
    MemoryDetailModal {
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
        on_delete: Callable[[], None] | None = None,
        on_complete: Callable[[], None] | None = None,
    ):
        super().__init__()
        self._memory_title = title
        self._memory_content = content
        self._on_delete = on_delete
        self._on_complete = on_complete
        self._confirming_delete = False

    def compose(self) -> ComposeResult:
        with Vertical(id="memory-detail-container"):
            yield Label(self._memory_title, id="memory-detail-title")
            yield RichLog(id="memory-detail-log", wrap=True, highlight=False, markup=False)
            yield Label(self._build_footer_text(), id="memory-detail-footer")

    def on_mount(self) -> None:
        self.query_one("#memory-detail-log", RichLog).write(self._memory_content)

    def on_key(self, event: events.Key) -> None:
        if event.key == "d" and self._on_delete:
            if self._confirming_delete:
                self._on_delete()
                self.dismiss()
            else:
                self._confirming_delete = True
                footer = self.query_one("#memory-detail-footer", Label)
                footer.update("Press D again to confirm deletion, any other key to cancel")
                footer.add_class("confirm")
            event.stop()
        elif event.key == "c" and self._on_complete:
            self._on_complete()
            self.dismiss()
            event.stop()
        elif self._confirming_delete:
            self._confirming_delete = False
            footer = self.query_one("#memory-detail-footer", Label)
            footer.update(self._build_footer_text())
            footer.remove_class("confirm")

    def _build_footer_text(self) -> str:
        actions: list[str] = []
        if self._on_complete:
            actions.append("C: complete")
        if self._on_delete:
            actions.append("D: delete")
        actions.append("Escape/Enter/Q: close")
        return "  |  ".join(actions)


class SidebarListView(ListView):
    """List view with keyboard navigation delegated to the app."""


class ChatInput(TextArea):
    """Wrapped chat composer that keeps messages single-paragraph on submit."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "submit", "Send", show=False, priority=True),
        Binding("ctrl+p", "command_palette", "Commands", show=False, priority=True),
        Binding("ctrl+m", "focus_memories", "Memories", priority=True),
        Binding("ctrl+a", "focus_agenda", "Agenda", priority=True),
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

    @property
    def elroy_app(self) -> ElroyApp:
        return cast("ElroyApp", self.app)

    def action_submit(self) -> None:
        self.elroy_app._submit_chat_input()

    def action_command_palette(self) -> None:
        self.elroy_app.action_command_palette()

    def action_focus_memories(self) -> None:
        self.elroy_app.action_focus_memories()

    def action_focus_agenda(self) -> None:
        self.elroy_app.action_focus_agenda()


class ElroyApp(App):
    """Main Textual TUI application for Elroy."""

    COMMANDS = App.COMMANDS | {ToolCommandProvider}
    DARK = True  # Force dark theme regardless of terminal preference
    SIDEBAR_SECTIONS: ClassVar[tuple[str, ...]] = ("memories", "agenda")
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

    #streaming-output {
        height: auto;
        min-height: 0;
        padding: 0 1;
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
        Binding("escape", "toggle_browse", "Browse", show=False),
        Binding("m", "focus_memories", "Memories", show=False),
        Binding("g", "focus_agenda", "Agenda", show=False),
    ]

    def __init__(
        self,
        ctx: ElroyContext,
        formatter: RichFormatter,
        enable_greeting: bool,
        show_internal_thought: bool,
    ):
        super().__init__()
        self.ctx = ctx
        self.formatter = formatter
        self.enable_greeting = enable_greeting
        self.io: ElroyIO = TextualIO(self, formatter, show_internal_thought)
        self.tool_command_specs = build_tool_command_specs(ctx)
        self._streaming_buffer = ""
        self._streaming_style = ""
        self._thought_buffer = ""
        self._memory_panel_visible = True
        self._browse_mode = False
        self._browse_target = "sidebar"
        self._panel_entries: dict[str, list[SidebarEntry]] = {buffer_name: [] for buffer_name in self.SIDEBAR_SECTIONS}
        self._panel_indices: dict[str, int | None] = dict.fromkeys(self.SIDEBAR_SECTIONS)
        self._input_history: list[str] = []
        self._history_index = -1
        self._spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._spinner_index = 0
        self._spinner_handle = None
        self._status_message = ""
        self._bg_status_handle = None
        self._chat_suggestions: list[str] = []
        self._active_worker_groups: set[str] = set()
        self._load_input_history()

    @property
    def chat_suggestions(self) -> list[str]:
        return self._chat_suggestions

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
            return "chat-stream" in self._active_worker_groups
        return None

    # ── history ──────────────────────────────────────────────────────────────

    def _load_input_history(self) -> None:
        try:
            p = Path(get_prompt_history_path())
            if p.exists():
                lines = p.read_text().splitlines()
                self._input_history = [ln[1:] for ln in reversed(lines) if ln.startswith("+")]
        except Exception:
            pass

    def _save_to_history(self, text: str) -> None:
        try:
            with Path(get_prompt_history_path()).open("a") as f:
                f.write(f"+{text}\n")
            self._input_history.insert(0, text)
        except Exception:
            pass

    # ── layout ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(id="conversation-container"):
            with Vertical(id="left-panel"):
                yield RichLog(id="history-log", wrap=True, highlight=False, markup=False)
                yield Static("", id="streaming-output")
            with Vertical(id="memory-panel"):
                yield Tabs(
                    Tab("Memories", id="memories-tab"),
                    Tab("Agenda", id="agenda-tab"),
                    active="memories-tab",
                    id="sidebar-tabs",
                )
                with ContentSwitcher(initial="memories-list", id="sidebar-switcher"):
                    yield SidebarListView(id="memories-list", classes="panel-list")
                    yield SidebarListView(id="agenda-list", classes="panel-list")
        yield ChatInput(placeholder="> ", id="chat-input")
        yield Label("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#chat-input", ChatInput).focus()
        self.call_after_refresh(self._resize_chat_input)

        from ..repository.user.queries import get_assistant_name

        self.title = get_assistant_name(self.ctx)
        self._render_status_bar()
        self._bg_status_handle = self.set_interval(1.0, self._tick_background_status)
        self._start_session()

    # ── commands ─────────────────────────────────────────────────────────────

    def get_tool_command_spec(self, name: str) -> ToolCommandSpec | None:
        return next((spec for spec in self.tool_command_specs if spec.name == name), None)

    def launch_tool_command(self, name: str, initial_values: dict[str, str] | None = None, source: str = "palette") -> None:
        spec = self.get_tool_command_spec(name)
        if spec is None:
            self._emit_error(f"Invalid command: {name}")
            return
        if spec.is_zero_arg and not initial_values:
            self._execute_tool_command(name, {}, source)
            return
        self.push_screen(
            CommandFormScreen(spec, initial_values),
            lambda values, spec_name=name, source_name=source: self._handle_command_form_result(spec_name, source_name, values),
        )

    def _handle_command_form_result(self, name: str, source: str, values: dict[str, str] | None) -> None:
        if values is None:
            return
        self._execute_tool_command(name, values, source)

    def _handle_slash_command(self, text: str) -> bool:
        command_name, raw_values = parse_slash_command(text)
        if not command_name:
            return True
        spec = self.get_tool_command_spec(command_name)
        if spec is None:
            self._emit_error(f"Invalid command: {command_name}. Open the command palette or use /help for available commands.")
            return True
        initial_values = build_initial_values(spec, raw_values)
        if spec.is_zero_arg or can_execute_from_values(spec, raw_values):
            self._execute_tool_command(spec.name, initial_values, "slash")
        else:
            self.launch_tool_command(spec.name, initial_values=initial_values, source="slash")
        return True

    @work(thread=True, group="command-action", exclusive=True, exit_on_error=False)
    def _execute_tool_command(self, name: str, values: dict[str, str], source: str) -> None:
        spec = self.get_tool_command_spec(name)
        if spec is None:
            self.call_from_thread(self._emit_error, f"Invalid command: {name}")
            return

        self.call_from_thread(self._set_input_disabled, True)
        self.call_from_thread(self._set_status_message, f"running /{spec.name}")
        try:
            result = execute_tool_command(spec, self.ctx, values)
            if isinstance(result, Iterator):
                self._run_stream(result)
            elif result is not None:
                self.call_from_thread(self._display_command_result, result, spec, source)
        except RecoverableToolError as exc:
            self.call_from_thread(self._emit_error, str(exc))
        finally:
            self.call_from_thread(self._set_input_disabled, False)
            self.call_from_thread(self._refresh_sidebar_state)
            self.call_from_thread(self._schedule_context_refresh)

    def _display_command_result(self, result, spec: ToolCommandSpec, source: str) -> None:
        if isinstance(result, str):
            if source == "palette" and spec.result_target == "toast" and "\n" not in result and len(result) <= 180:
                self.notify(result)
            else:
                self._write_to_history(Text(result, style=self.formatter.system_message_color))
        else:
            self._write_to_history(result)

    # ── memory panel ─────────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        section = self._section_for_list(event.list_view)
        if section is None or event.index is None:
            return
        self._panel_indices[section] = event.index
        self._browse_target = "sidebar"
        self._open_panel_entry(section, event.index)
        self._render_browse_state()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        section = self._section_for_list(event.list_view)
        if section is None:
            return
        self._panel_indices[section] = event.list_view.index
        self._browse_target = "sidebar"
        self._render_browse_state()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        section = self._section_for_tab_id(event.tab.id or "")
        if section is None:
            return
        self.query_one("#sidebar-switcher", ContentSwitcher).current = self._list_id(section)
        self.call_after_refresh(self._ensure_panel_index, section)
        if self._browse_mode and self._browse_target == "sidebar":
            self._current_sidebar_list().focus()
        self._render_browse_state()

    # ── session init ─────────────────────────────────────────────────────────

    @work(thread=True, group="session-bootstrap", exclusive=True, exit_on_error=False)
    def _start_session(self) -> None:
        from ..cli.chat import get_session_context
        from ..messenger.messenger import process_message
        from ..repository.context_messages.factory import build_context_message_read_store, build_context_refresh_orchestrator
        from ..repository.context_messages.tools import to_synthetic_tool_call
        from ..repository.context_messages.transforms import get_time_since_most_recent_user_message
        from ..repository.context_messages.validations import Validator

        context_refresh_orchestrator = build_context_refresh_orchestrator(self.ctx)
        context_refresh_orchestrator.add_context_messages(to_synthetic_tool_call("get_session_context", get_session_context(self.ctx)))
        context_messages = list(Validator(self.ctx, build_context_message_read_store(self.ctx).get_context_messages()).validated_msgs())
        self.call_from_thread(self._render_existing_context_messages, context_messages)

        if self.enable_greeting and (
            (get_time_since_most_recent_user_message(context_messages) or timedelta()) >= self.ctx.min_convo_age_for_greeting
        ):
            self._run_stream(process_message(role=USER, ctx=self.ctx, msg="<Empty user response>", enable_tools=False))

        self.call_from_thread(self._refresh_sidebar_state)

    # ── streaming helpers ─────────────────────────────────────────────────────

    def _run_stream(self, stream: Iterator) -> None:
        """Consume a message stream from a worker thread."""
        from ..llm.stream_parser import StatusUpdate

        worker = get_current_worker()
        self.call_from_thread(self._set_input_disabled, True)
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
            self.call_from_thread(self._set_input_disabled, False)

    def _append_streaming_token(self, token: str, style: str) -> None:
        self._streaming_buffer += token
        self._streaming_style = style
        self.query_one("#streaming-output", Static).update(Text(self._streaming_buffer, style=style))

    def _flush_streaming_buffer(self) -> None:
        if self._streaming_buffer:
            self._write_to_history(Text(self._streaming_buffer, style=self._streaming_style))
            self._streaming_buffer = ""
            self._streaming_style = ""
        self.query_one("#streaming-output", Static).update("")

    def _append_thought_token(self, token: str) -> None:
        self._thought_buffer += token

    def _flush_thought_buffer(self) -> None:
        if self._thought_buffer:
            style = f"italic {self.formatter.internal_thought_color}"
            self._write_to_history(Text(self._thought_buffer, style=style))
            self._thought_buffer = ""

    def _write_to_history(self, renderable) -> None:
        self.query_one("#history-log", RichLog).write(renderable)

    def _render_existing_context_messages(self, context_messages: list) -> None:
        bootstrap_tool_call_ids = {
            tool_call.id
            for message in context_messages
            if message.role == ASSISTANT and message.tool_calls
            for tool_call in message.tool_calls
            if tool_call.function.get("name") == "get_session_context"
        }

        for message in context_messages:
            if message.role == SYSTEM:
                continue
            if (
                message.role == ASSISTANT
                and message.tool_calls
                and any(tool_call.id in bootstrap_tool_call_ids for tool_call in message.tool_calls)
            ):
                continue
            if message.role == TOOL and message.tool_call_id in bootstrap_tool_call_ids:
                continue
            if not message.content:
                continue

            if message.role == USER:
                renderable = Text(f"\nYou: {message.content}", style=self.formatter.user_input_color)
            elif message.role == ASSISTANT:
                renderable = Text(message.content, style=self.formatter.assistant_message_color)
            elif message.role == TOOL:
                renderable = Text(message.content, style=self.formatter.system_message_color)
            else:
                renderable = Text(message.content, style=self.formatter.system_message_color)

            self._write_to_history(renderable)

    def _set_input_disabled(self, disabled: bool) -> None:
        input_widget = self.query_one("#chat-input", ChatInput)
        input_widget.disabled = disabled
        if not disabled:
            self._focus_chat_input()

    # ── input handling ────────────────────────────────────────────────────────

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "chat-input":
            self.call_after_refresh(self._resize_chat_input)

    def _submit_chat_input(self) -> None:
        text = self.query_one("#chat-input", ChatInput).value.strip()
        if not text:
            return

        self.query_one("#chat-input", ChatInput).value = ""
        self._resize_chat_input()

        self._save_to_history(text)
        self._history_index = -1

        if text.lower() in (EXIT, f"/{EXIT}"):
            self.exit()
            return

        self._write_to_history(Text(f"\nYou: {text}", style=self.formatter.user_input_color))
        if text.startswith("/") and not text.lower().startswith("/ask"):
            self._handle_slash_command(text)
            return

        msg = re.sub(r"^/ask\s*", "", text).strip() if text.lower().startswith("/ask") else text
        self._process_chat_message(msg)

    def on_key(self, event: events.Key) -> None:
        input_widget = self.query_one("#chat-input", ChatInput)
        history_log = self.query_one("#history-log", RichLog)
        if self.screen is not self.screen_stack[0]:
            return

        if event.key == "ctrl+d":
            self.exit()
            event.prevent_default()
            event.stop()
            return
        if event.key == "ctrl+c":
            self.action_cancel_stream()
            event.prevent_default()
            event.stop()
            return
        if event.key == "ctrl+m":
            self.action_focus_memories()
            event.prevent_default()
            event.stop()
            return
        if event.key == "ctrl+a":
            self.action_focus_agenda()
            event.prevent_default()
            event.stop()
            return
        if event.key == "escape":
            self._toggle_mode()
            event.prevent_default()
            event.stop()
            return

        if self._browse_mode:
            handled = self._handle_browse_key(event, history_log)
            if handled:
                return
        elif input_widget.has_focus:
            handled = self._handle_chat_key(event, input_widget)
            if handled:
                return

        current_sidebar = self._current_sidebar_list()
        if not input_widget.has_focus and not history_log.has_focus and not current_sidebar.has_focus:
            self._focus_chat_input()
            event.prevent_default()

    @work(thread=True, group="chat-stream", exclusive=True, exit_on_error=False)
    def _process_chat_message(self, text: str) -> None:
        from ..messenger.messenger import process_message

        self.call_from_thread(self._set_status_message, "thinking...")
        try:
            self._run_stream(process_message(role=USER, ctx=self.ctx, msg=text))
        except Exception as exc:
            self.call_from_thread(self._emit_error, str(exc))
            logger.exception("Error processing chat input")
        finally:
            self.call_from_thread(self._refresh_sidebar_state)
            self.call_from_thread(self._schedule_context_refresh)

    # ── actions ───────────────────────────────────────────────────────────────

    def action_cancel_stream(self) -> None:
        if "chat-stream" in self._active_worker_groups:
            self.workers.cancel_group(self, "chat-stream")
            self._flush_streaming_buffer()
            self._set_input_disabled(False)
            self.ctx.db.rollback()

    def action_toggle_browse(self) -> None:
        self._toggle_mode()

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
            state = AgendaPresenter(self.ctx).build_sidebar_state()
            self.call_from_thread(self._apply_sidebar_state, state)
        except Exception:
            logger.debug("Failed to refresh sidebar state", exc_info=True)

    def _apply_sidebar_state(self, state: SidebarState) -> None:
        self._panel_entries = {"memories": state.memories, "agenda": state.agenda}
        self._chat_suggestions = state.completions
        self._render_sidebar_lists()

    @work(thread=True, group="deferred-context-refresh", exclusive=True, exit_on_error=False)
    def _deferred_context_refresh(self) -> None:
        from ..repository.context_messages.factory import build_context_refresh_orchestrator

        try:
            build_context_refresh_orchestrator(self.ctx).refresh_context_if_needed()
        except Exception:
            logger.debug("Deferred context refresh failed", exc_info=True)

    def _schedule_context_refresh(self) -> None:
        self.set_timer(5.0, self._deferred_context_refresh)

    # ── worker state / status ────────────────────────────────────────────────

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        group = getattr(event.worker, "group", "default")
        if group not in {"session-bootstrap", "chat-stream", "sidebar-refresh", "command-action", "deferred-context-refresh"}:
            return

        if event.state == WorkerState.RUNNING:
            self._active_worker_groups.add(group)
            if group == "sidebar-refresh":
                self._set_status_message("refreshing sidebar")
            elif group == "command-action":
                self._set_status_message("running command")
            self._render_status_bar()
            return

        self._active_worker_groups.discard(group)
        if event.state == WorkerState.ERROR and event.worker.error:
            self._emit_error(str(event.worker.error))
        elif event.state == WorkerState.CANCELLED and group == "chat-stream":
            self.notify("Chat stream cancelled")
        self._render_status_bar()

    def _start_spinner(self) -> None:
        self._spinner_index = 0
        if self._spinner_handle:
            self._spinner_handle.stop()
        self._spinner_handle = self.set_interval(0.08, self._tick_spinner)

    def _tick_spinner(self) -> None:
        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_chars)
        self._render_status_bar()

    def _set_status_message(self, message: str) -> None:
        self._status_message = message
        self._render_status_bar()

    def _stop_spinner(self) -> None:
        if self._spinner_handle:
            self._spinner_handle.stop()
            self._spinner_handle = None
        self._render_status_bar()

    def _tick_background_status(self) -> None:
        if "chat-stream" not in self._active_worker_groups:
            self._render_status_bar()

    def _emit_error(self, message: str) -> None:
        self.notify(message, severity="error")
        self._write_to_history(Text(f"Error: {message}", style=self.formatter.warning_color))

    # ── focus / browse helpers ───────────────────────────────────────────────

    def _handle_chat_key(self, event: events.Key, input_widget: ChatInput) -> bool:
        if event.key == "enter":
            self._submit_chat_input()
            event.prevent_default()
            event.stop()
            return True

        if event.key == "up":
            if self._input_history and self._history_index < len(self._input_history) - 1:
                self._history_index += 1
                input_widget.value = self._input_history[self._history_index]
            event.prevent_default()
            event.stop()
            return True

        if event.key == "down":
            if self._history_index > 0:
                self._history_index -= 1
                input_widget.value = self._input_history[self._history_index]
            elif self._history_index == 0:
                self._history_index = -1
                input_widget.value = ""
            event.prevent_default()
            event.stop()
            return True

        if event.key == "tab":
            self._accept_input_completion()
            event.prevent_default()
            event.stop()
            return True

        return False

    def _handle_browse_key(self, event: events.Key, history_log: RichLog) -> bool:
        if event.key in {"j", "down"}:
            if self._browse_target == "history":
                history_log.scroll_down(animate=False, immediate=True)
            else:
                self._move_sidebar_selection(1)
        elif event.key in {"k", "up"}:
            if self._browse_target == "history":
                history_log.scroll_up(animate=False, immediate=True)
            else:
                self._move_sidebar_selection(-1)
        elif event.key == "tab":
            self._cycle_browse_target()
        elif event.key == "m":
            self._switch_sidebar_section("memories")
        elif event.key == "g":
            self._switch_sidebar_section("agenda")
        elif event.key == "enter":
            if self._browse_target == "sidebar":
                list_widget = self._current_sidebar_list()
                index = list_widget.index
                if index is not None:
                    self._open_panel_entry(self.current_sidebar_section, index)
        elif event.key in {"escape", "i", "a"}:
            self._focus_chat_input()
        else:
            return False

        event.prevent_default()
        event.stop()
        return True

    def _toggle_mode(self) -> None:
        if self._browse_mode:
            self._focus_chat_input()
        else:
            self._focus_browse_target()

    @property
    def current_sidebar_section(self) -> str:
        active = self.query_one("#sidebar-tabs", Tabs).active or "memories-tab"
        return self._section_for_tab_id(active) or "memories"

    def _focus_chat_input(self) -> None:
        self._browse_mode = False
        self.query_one("#chat-input", ChatInput).focus()
        self._render_browse_state()

    def _resize_chat_input(self) -> None:
        input_widget = self.query_one("#chat-input", ChatInput)
        content_height = max(1, input_widget.virtual_size.height)
        input_widget.styles.height = max(3, min(8, content_height + 2))

    def _focus_browse_target(self) -> None:
        self._browse_mode = True
        if self._browse_target == "history":
            self.query_one("#history-log", RichLog).focus()
        else:
            self._current_sidebar_list().focus()
            self._ensure_panel_index(self.current_sidebar_section)
        self._render_browse_state()

    def _cycle_browse_target(self) -> None:
        self._browse_target = "history" if self._browse_target == "sidebar" else "sidebar"
        self._focus_browse_target()

    def _render_sidebar_lists(self) -> None:
        for section in self.SIDEBAR_SECTIONS:
            list_view = self._sidebar_list(section)
            list_view.clear()
            entries = self._panel_entries[section]
            list_view.extend([ListItem(Label(entry.title), name=entry.lookup_key) for entry in entries])
            self.call_after_refresh(self._ensure_panel_index, section)
        self._render_browse_state()

    def _ensure_panel_index(self, section: str) -> None:
        list_view = self._sidebar_list(section)
        entries = self._panel_entries[section]
        if not entries:
            self._panel_indices[section] = None
            list_view.index = None
            return

        saved_index = self._panel_indices[section]
        if saved_index is None:
            saved_index = 0
        saved_index = max(0, min(saved_index, len(entries) - 1))
        self._panel_indices[section] = saved_index
        list_view.index = saved_index
        self._sync_sidebar_highlight(section, saved_index)

    def _move_sidebar_selection(self, delta: int) -> None:
        section = self.current_sidebar_section
        list_view = self._sidebar_list(section)
        entries = self._panel_entries[section]
        if not entries:
            self._panel_indices[section] = None
            list_view.index = None
            return

        current_index = self._panel_indices[section]
        if current_index is None:
            current_index = list_view.index if list_view.index is not None else 0

        next_index = max(0, min(current_index + delta, len(entries) - 1))
        self._panel_indices[section] = next_index
        list_view.index = next_index
        self._sync_sidebar_highlight(section, next_index)

    def _sync_sidebar_highlight(self, section: str, active_index: int | None) -> None:
        list_view = self._sidebar_list(section)
        items = [child for child in list_view.children if isinstance(child, ListItem)]
        for index, item in enumerate(items):
            item.highlighted = active_index is not None and index == active_index

    def _switch_sidebar_section(self, section: str, focus_sidebar: bool = False) -> None:
        if section not in self._panel_entries:
            return
        self.query_one("#sidebar-tabs", Tabs).active = self._tab_id(section)
        self.query_one("#sidebar-switcher", ContentSwitcher).current = self._list_id(section)
        self._ensure_panel_index(section)
        if focus_sidebar:
            self._browse_mode = True
            self._browse_target = "sidebar"
            self._current_sidebar_list().focus()
        elif self._browse_mode:
            self._browse_target = "sidebar"
            self._current_sidebar_list().focus()
        self._render_browse_state()

    def _open_panel_entry(self, section: str, index: int) -> None:
        entries = self._panel_entries[section]
        if not (0 <= index < len(entries)):
            return

        entry = entries[index]
        presenter = AgendaPresenter(self.ctx)
        if section == "memories":
            modal = presenter.build_memory_modal(entry, self._refresh_sidebar_state)
            if modal is None:
                return
        else:
            modal = presenter.build_agenda_modal(entry, self._refresh_sidebar_state)

        assert isinstance(modal, ModalSpec)
        self.push_screen(MemoryDetailModal(modal.title, modal.content, on_delete=modal.on_delete, on_complete=modal.on_complete))

    def _accept_input_completion(self) -> None:
        input_widget = self.query_one("#chat-input", ChatInput)
        if input_widget.cursor_location[1] != len(input_widget.value):
            return

        prefix = input_widget.value
        if not prefix:
            return

        match = next(
            (suggestion for suggestion in self._chat_suggestions if suggestion.lower().startswith(prefix.lower()) and suggestion != prefix),
            None,
        )
        if match:
            input_widget.value = match

    def _render_browse_state(self) -> None:
        left_panel = self.query_one("#left-panel", Vertical)
        history_active = self._browse_mode and self._browse_target == "history"
        left_panel.set_class(history_active, "active")
        for section in self.SIDEBAR_SECTIONS:
            sidebar = self._sidebar_list(section)
            sidebar_active = self._browse_mode and self._browse_target == "sidebar" and self.current_sidebar_section == section
            sidebar.set_class(sidebar_active, "active")
        self._render_status_bar()

    def _render_status_bar(self) -> None:
        import contextlib

        from ..core.status import get_background_status

        try:
            model_name = self.ctx.chat_model.name
        except Exception:
            return

        if "chat-stream" in self._active_worker_groups:
            prefix = f"{self._spinner_chars[self._spinner_index]} {self._status_message or 'thinking...'}"
        elif self._active_worker_groups:
            active = ", ".join(sorted(self._active_worker_groups))
            prefix = f"● {model_name}  ⟳ {active}"
        else:
            bg = get_background_status()
            prefix = f"● {model_name}  ⟳ {bg}" if bg else f"● {model_name}"

        with contextlib.suppress(Exception):
            self.query_one("#status-bar", Label).update(prefix)

    def _section_for_list(self, list_view: ListView) -> str | None:
        return {self._list_id(section): section for section in self.SIDEBAR_SECTIONS}.get(list_view.id or "")

    def _section_for_tab_id(self, tab_id: str) -> str | None:
        return {self._tab_id(section): section for section in self.SIDEBAR_SECTIONS}.get(tab_id)

    def _tab_id(self, section: str) -> str:
        return f"{section}-tab"

    def _list_id(self, section: str) -> str:
        return f"{section}-list"

    def _sidebar_list(self, section: str) -> SidebarListView:
        return self.query_one(f"#{self._list_id(section)}", SidebarListView)

    def _current_sidebar_list(self) -> SidebarListView:
        return self._sidebar_list(self.current_sidebar_section)


def make_app(**overrides) -> ElroyApp:
    """Create an ElroyApp from resolved config/env, with optional overrides."""
    from ..cli.options import get_resolved_params
    from ..core.ctx import ElroyContext

    params = get_resolved_params(**overrides)
    ctx = ElroyContext.init(use_background_threads=True, **params)
    formatter = RichFormatter(
        system_message_color=params["system_message_color"],
        assistant_message_color=params["assistant_color"],
        user_input_color=params["user_input_color"],
        warning_color=params["warning_color"],
        internal_thought_color=params["internal_thought_color"],
    )
    return ElroyApp(
        ctx=ctx,
        formatter=formatter,
        enable_greeting=params.get("enable_assistant_greeting", False),
        show_internal_thought=params.get("show_internal_thought", False),
    )


def _handle_cli_command(argv: list[str]) -> bool:
    if not argv:
        return False

    if argv[0] in {"version", "--version", "-V"}:
        print(__version__)
        return True

    return False


def main(argv: list[str] | None = None) -> None:
    from ..core.logging import setup_file_logging
    from ..core.session import init_elroy_session

    if _handle_cli_command(list(sys.argv[1:] if argv is None else argv)):
        return

    setup_file_logging()
    app = make_app()
    with init_elroy_session(app.ctx, app.io, check_db_migration=True, should_onboard_interactive=False):
        app.run()


if __name__ == "__main__":
    main()
