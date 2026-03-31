"""Textual TUI for Elroy chat interface."""

import re
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import ClassVar, cast

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.suggester import SuggestFromList
from textual.widgets import Input, Label, ListItem, ListView, RichLog, Static

from ..config.paths import get_prompt_history_path
from ..core.constants import EXIT, USER
from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..io.base import ElroyIO
from ..io.completions import build_completions, get_memory_panel_entries
from ..io.formatters.rich_formatter import RichFormatter
from ..io.textual_io import TextualIO

logger = get_logger()


@dataclass
class RightPanelEntry:
    """A browseable sidebar row and the content behind it."""

    title: str
    lookup_key: str
    content: str
    deletable: bool = False


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

    BINDINGS = [Binding("escape,enter,q", "dismiss", "Close", show=False)]

    def __init__(self, title: str, content: str, on_delete: "Callable[[], None] | None" = None):
        super().__init__()
        self._memory_title = title
        self._memory_content = content
        self._on_delete = on_delete
        self._confirming_delete = False

    def compose(self) -> ComposeResult:
        with Vertical(id="memory-detail-container"):
            yield Label(self._memory_title, id="memory-detail-title")
            yield RichLog(id="memory-detail-log", wrap=True, highlight=False, markup=False)
            footer_text = "D: delete  |  Escape/Enter/Q: close" if self._on_delete else "Escape/Enter/Q: close"
            yield Label(footer_text, id="memory-detail-footer")

    def on_mount(self) -> None:
        self.query_one("#memory-detail-log", RichLog).write(self._memory_content)

    def on_key(self, event) -> None:
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
        elif self._confirming_delete:
            self._confirming_delete = False
            footer = self.query_one("#memory-detail-footer", Label)
            footer.update("D: delete  |  Escape/Enter/Q: close")
            footer.remove_class("confirm")


class ElroyApp(App):
    """Main Textual TUI application for Elroy."""

    DARK = True  # Force dark theme regardless of terminal preference
    BROWSE_BUFFERS: ClassVar[tuple[str, ...]] = ("memories", "reminders", "agenda")
    BUFFER_TITLES: ClassVar[dict[str, str]] = {
        "memories": "Memories",
        "reminders": "Reminders",
        "agenda": "Agenda",
    }
    MEMORY_BUFFER_SOURCE_TYPES: ClassVar[set[str]] = {"Memory", "DocumentExcerpt", "ContextMessageSet"}

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

    #memory-panel.hidden {
        display: none;
    }

    #memory-title {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
        text-align: center;
    }

    #memory-list {
        height: 1fr;
    }

    #chat-input {
        height: 3;
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
        Binding("ctrl+d", "quit", "Exit"),
        Binding("ctrl+c", "cancel_stream", "Cancel", show=False),
        Binding("f2", "toggle_memory", "Memory Panel"),
    ]

    def __init__(
        self,
        ctx: ElroyContext,
        formatter: RichFormatter,
        enable_greeting: bool,
        show_internal_thought: bool,
        show_memory_panel: bool,
    ):
        super().__init__()
        self.ctx = ctx
        self.formatter = formatter
        self.enable_greeting = enable_greeting
        self.io: ElroyIO = TextualIO(self, formatter, show_internal_thought)
        self._streaming = False
        self._streaming_buffer = ""
        self._streaming_style = ""
        self._thought_buffer = ""
        self._memory_panel_visible = show_memory_panel
        self._browse_mode = False
        self._browse_buffer = "memories"
        self._panel_entries: dict[str, list[RightPanelEntry]] = {buffer_name: [] for buffer_name in self.BROWSE_BUFFERS}
        self._panel_indices: dict[str, int | None] = dict.fromkeys(self.BROWSE_BUFFERS)
        self._input_history: list[str] = []
        self._history_index = -1
        self._spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._spinner_index = 0
        self._spinner_handle = None
        self._status_message = "thinking..."
        self._bg_status_handle = None
        self._load_input_history()

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
            with open(get_prompt_history_path(), "a") as f:
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
                yield Label("Memories", id="memory-title")
                yield ListView(id="memory-list")
        yield Input(placeholder="> ", id="chat-input")
        yield Label("", id="status-bar")

    def on_mount(self) -> None:
        if not self._memory_panel_visible:
            self.query_one("#memory-panel").add_class("hidden")

        self.query_one("#chat-input").focus()

        from ..repository.user.queries import get_assistant_name

        self.title = get_assistant_name(self.ctx)
        self._stop_spinner()  # initialise status bar with model name
        self._bg_status_handle = self.set_interval(1.0, self._tick_background_status)
        self._start_session()

    # ── memory panel ─────────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "memory-list":
            return
        if event.index is None:
            return
        self._panel_indices[self._browse_buffer] = event.index
        self._open_panel_entry(event.index)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "memory-list":
            return
        self._panel_indices[self._browse_buffer] = event.list_view.index

    # ── session init ─────────────────────────────────────────────────────────

    @work(thread=True)
    def _start_session(self) -> None:
        from ..cli.chat import get_session_context
        from ..messenger.messenger import process_message
        from ..repository.context_messages.operations import add_context_messages
        from ..repository.context_messages.queries import get_context_messages
        from ..repository.context_messages.tools import to_synthetic_tool_call
        from ..repository.context_messages.transforms import get_time_since_most_recent_user_message
        from ..repository.context_messages.validations import Validator

        add_context_messages(self.ctx, to_synthetic_tool_call("get_session_context", get_session_context(self.ctx)))
        context_messages = Validator(self.ctx, get_context_messages(self.ctx)).validated_msgs()

        if self.enable_greeting and (
            (get_time_since_most_recent_user_message(context_messages) or timedelta()) >= self.ctx.min_convo_age_for_greeting
        ):
            self._run_stream(process_message(role=USER, ctx=self.ctx, msg="<Empty user response>", enable_tools=False))

        self._refresh_memory_panel()
        self._update_completions()

    # ── streaming helpers ─────────────────────────────────────────────────────

    def _run_stream(self, stream: Iterator) -> None:
        """Consume a message stream (call from worker thread)."""
        from ..llm.stream_parser import StatusUpdate

        self._streaming = True
        self.call_from_thread(self._set_input_disabled, True)
        self.call_from_thread(self._start_spinner)
        try:
            for item in stream:
                if isinstance(item, StatusUpdate):
                    self._status_message = item.content
                    self.call_from_thread(self._update_spinner_text)
                else:
                    self.io.print(item, end="")
        finally:
            self.call_from_thread(self._flush_thought_buffer)
            self.call_from_thread(self._flush_streaming_buffer)
            self._streaming = False
            self.call_from_thread(self._stop_spinner)
            self.call_from_thread(self._set_input_disabled, False)

    def _append_streaming_token(self, token: str, style: str) -> None:
        """Append a token to the live streaming area (main thread)."""
        self._streaming_buffer += token
        self._streaming_style = style
        self.query_one("#streaming-output", Static).update(Text(self._streaming_buffer, style=style))

    def _flush_streaming_buffer(self) -> None:
        """Move the streaming buffer into the history log (main thread)."""
        if self._streaming_buffer:
            self._write_to_history(Text(self._streaming_buffer, style=self._streaming_style))
            self._streaming_buffer = ""
            self._streaming_style = ""
        self.query_one("#streaming-output", Static).update("")

    def _append_thought_token(self, token: str) -> None:
        """Accumulate an internal-thought token (main thread)."""
        self._thought_buffer += token

    def _flush_thought_buffer(self) -> None:
        """Write the accumulated thought as a single line to history (main thread)."""
        if self._thought_buffer:
            style = f"italic {self.formatter.internal_thought_color}"
            self._write_to_history(Text(self._thought_buffer, style=style))
            self._thought_buffer = ""

    def _write_to_history(self, renderable) -> None:
        """Write a Rich renderable to the history log (main thread)."""
        self.query_one("#history-log", RichLog).write(renderable)

    def _set_input_disabled(self, disabled: bool) -> None:
        input_widget = self.query_one("#chat-input", Input)
        input_widget.disabled = disabled
        if not disabled:
            self._focus_chat_input()

    # ── input handling ────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        self.query_one("#chat-input", Input).value = ""

        self._save_to_history(text)
        self._history_index = -1

        if text.lower() in (EXIT, f"/{EXIT}"):
            self.exit()
            return

        self._write_to_history(Text(f"\nYou: {text}", style=self.formatter.user_input_color))
        self._process_input(text)

    def on_key(self, event) -> None:
        input_widget = self.query_one("#chat-input", Input)
        list_widget = self.query_one("#memory-list", ListView)
        if self.screen is not self.screen_stack[0]:
            return

        if event.key == "escape":
            self._toggle_mode()
            event.prevent_default()
            event.stop()
            return

        if self._browse_mode:
            handled = self._handle_browse_key(event, list_widget)
            if handled:
                return
        elif input_widget.has_focus:
            handled = self._handle_chat_key(event, input_widget)
            if handled:
                return

        if not input_widget.has_focus and not list_widget.has_focus:
            self._focus_chat_input()
            event.prevent_default()

    @work(thread=True, exclusive=True)
    def _process_input(self, text: str) -> None:
        """Process user input in a background thread."""
        from ..messenger.messenger import process_message
        from ..messenger.slash_commands import invoke_slash_command

        try:
            if text.startswith("/") and not text.lower().startswith("/ask"):
                try:
                    result = invoke_slash_command(self.io, self.ctx, text)
                    if isinstance(result, (Iterator, AsyncIterator)):
                        self._run_stream(cast(Iterator, result))
                    elif result is not None:
                        self.call_from_thread(self._write_to_history, Text(str(result), style=self.formatter.system_message_color))
                except Exception as e:
                    self.call_from_thread(self._write_to_history, Text(f"Error: {e}", style=self.formatter.warning_color))
            else:
                msg = re.sub(r"^/ask\s*", "", text).strip() if text.lower().startswith("/ask") else text
                self._run_stream(process_message(role=USER, ctx=self.ctx, msg=msg))
        except Exception as e:
            self.call_from_thread(self._write_to_history, Text(f"Error: {e}", style=self.formatter.warning_color))
            logger.exception("Error processing input")
        finally:
            self._refresh_memory_panel()
            self._update_completions()
            from ..core.async_tasks import schedule_task
            from ..repository.context_messages.operations import refresh_context_if_needed

            schedule_task(refresh_context_if_needed, self.ctx, replace=True, delay_seconds=5)

    # ── actions ───────────────────────────────────────────────────────────────

    def action_cancel_stream(self) -> None:
        if self._streaming:
            self.workers.cancel_all()
            self._streaming = False
            self._flush_streaming_buffer()
            self._set_input_disabled(False)
            self.ctx.db.rollback()

    def action_toggle_memory(self) -> None:
        panel = self.query_one("#memory-panel")
        self._memory_panel_visible = not self._memory_panel_visible
        if self._memory_panel_visible:
            panel.remove_class("hidden")
            if self._browse_mode:
                self._focus_browse_list()
        else:
            panel.add_class("hidden")
            if self._browse_mode:
                self._focus_chat_input()

    # ── periodic updates ──────────────────────────────────────────────────────

    @work(thread=True)
    def _refresh_memory_panel(self) -> None:
        try:
            from ..config.paths import get_agenda_dir
            from ..repository.agenda.file_storage import list_agenda_items
            from ..repository.reminders.queries import get_active_reminders
            from ..utils.clock import db_time_to_local

            memory_entries = []
            for display_name, type_key in get_memory_panel_entries(self.ctx):
                source_type, _, _ = type_key.partition(": ")
                if source_type not in self.MEMORY_BUFFER_SOURCE_TYPES:
                    continue
                memory_entries.append(RightPanelEntry(title=display_name, lookup_key=type_key, content=""))
                if len(memory_entries) >= 15:
                    break
            reminder_entries = []
            for reminder in get_active_reminders(self.ctx)[:15]:
                if reminder.trigger_datetime:
                    when = db_time_to_local(reminder.trigger_datetime).strftime("%Y-%m-%d %H:%M")
                    title = f"{reminder.name} [{when}]"
                elif reminder.reminder_context:
                    title = f"{reminder.name} [context]"
                else:
                    title = reminder.name
                reminder_entries.append(
                    RightPanelEntry(
                        title=title,
                        lookup_key=reminder.name,
                        content=reminder.to_fact(),
                        deletable=True,
                    )
                )
            agenda_entries = [
                RightPanelEntry(title=path.stem, lookup_key=str(path), content=text)
                for path, _, text in list_agenda_items(get_agenda_dir())[:15]
            ]
            self._panel_entries = {
                "memories": memory_entries,
                "reminders": reminder_entries,
                "agenda": agenda_entries,
            }
            self.call_from_thread(self._render_current_panel)
        except Exception:
            logger.debug("Failed to refresh memory panel", exc_info=True)

    @work(thread=True)
    def _update_completions(self) -> None:
        try:
            suggestions = build_completions(self.ctx)
            input_widget = self.query_one("#chat-input", Input)
            self.call_from_thread(setattr, input_widget, "suggester", SuggestFromList(suggestions, case_sensitive=False))
        except Exception:
            logger.debug("Failed to update completions", exc_info=True)

    def _start_spinner(self) -> None:
        self._spinner_index = 0
        self._status_message = "thinking..."
        if self._spinner_handle:
            self._spinner_handle.stop()
        self._spinner_handle = self.set_interval(0.08, self._tick_spinner)

    def _tick_spinner(self) -> None:
        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_chars)
        self._render_status_bar()

    def _update_spinner_text(self) -> None:
        """Immediately refresh the status bar text without advancing the spinner frame."""
        self._render_status_bar()

    def _stop_spinner(self) -> None:
        if self._spinner_handle:
            self._spinner_handle.stop()
            self._spinner_handle = None
        self._status_message = "thinking..."
        self._update_idle_status()

    def _update_idle_status(self) -> None:
        """Refresh the status bar when not streaming, incorporating background task status."""
        self._render_status_bar()

    def _tick_background_status(self) -> None:
        """Periodically update the idle status bar with background task activity."""
        if not self._streaming:
            self._update_idle_status()

    # ── focus / browse helpers ───────────────────────────────────────────────

    def _handle_chat_key(self, event, input_widget: Input) -> bool:
        if event.key == "up":
            if self._input_history and self._history_index < len(self._input_history) - 1:
                self._history_index += 1
                input_widget.value = self._input_history[self._history_index]
                input_widget.cursor_position = len(input_widget.value)
            event.prevent_default()
            event.stop()
            return True

        if event.key == "down":
            if self._history_index > 0:
                self._history_index -= 1
                input_widget.value = self._input_history[self._history_index]
                input_widget.cursor_position = len(input_widget.value)
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

    def _handle_browse_key(self, event, list_widget: ListView) -> bool:
        if event.key in {"j", "down"}:
            list_widget.action_cursor_down()
        elif event.key in {"k", "up"}:
            list_widget.action_cursor_up()
        elif event.key == "tab":
            self._cycle_browse_buffer(1)
        elif event.key == "shift+tab":
            self._cycle_browse_buffer(-1)
        elif event.key == "enter":
            index = list_widget.index
            if index is not None:
                self._open_panel_entry(index)
        elif event.key in {"i", "a"}:
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
            self._focus_browse_list()

    def _focus_chat_input(self) -> None:
        self._browse_mode = False
        self.query_one("#chat-input", Input).focus()
        self._render_status_bar()

    def _focus_browse_list(self) -> None:
        if not self._memory_panel_visible:
            self.query_one("#memory-panel").remove_class("hidden")
            self._memory_panel_visible = True
        self._browse_mode = True
        list_widget = self.query_one("#memory-list", ListView)
        list_widget.focus()
        self._ensure_panel_index()
        self._render_status_bar()

    def _cycle_browse_buffer(self, direction: int) -> None:
        current_index = self.BROWSE_BUFFERS.index(self._browse_buffer)
        self._browse_buffer = self.BROWSE_BUFFERS[(current_index + direction) % len(self.BROWSE_BUFFERS)]
        self._render_current_panel()
        self._focus_browse_list()

    def _render_current_panel(self) -> None:
        list_view = self.query_one("#memory-list", ListView)
        title = self.BUFFER_TITLES[self._browse_buffer]
        entries = self._panel_entries[self._browse_buffer]
        self.query_one("#memory-title", Label).update(title)
        list_view.clear()
        list_view.extend([ListItem(Label(entry.title), name=entry.lookup_key) for entry in entries])
        self.call_after_refresh(self._ensure_panel_index)
        self._render_status_bar()

    def _ensure_panel_index(self) -> None:
        list_view = self.query_one("#memory-list", ListView)
        entries = self._panel_entries[self._browse_buffer]
        if not entries:
            self._panel_indices[self._browse_buffer] = None
            list_view.index = None
            return
        saved_index = self._panel_indices[self._browse_buffer]
        if saved_index is None:
            saved_index = 0
        saved_index = max(0, min(saved_index, len(entries) - 1))
        self._panel_indices[self._browse_buffer] = saved_index
        list_view.index = saved_index

    def _open_panel_entry(self, index: int) -> None:
        entries = self._panel_entries[self._browse_buffer]
        if not (0 <= index < len(entries)):
            return
        entry = entries[index]
        on_delete = None
        if self._browse_buffer == "memories":
            from ..db.db_models import EmbeddableSqlModel
            from ..repository.memories.operations import mark_inactive
            from ..repository.memories.queries import db_get_memory_source_by_name

            type_key = entry.lookup_key
            if ": " not in type_key:
                return
            source_type, name = type_key.split(": ", 1)
            source = db_get_memory_source_by_name(self.ctx, source_type, name)
            if not source:
                return
            content = source.to_fact()
            if isinstance(source, EmbeddableSqlModel):

                def on_delete(s=source) -> None:
                    mark_inactive(self.ctx, s)
                    self._refresh_memory_panel()

            title = name
        elif self._browse_buffer == "reminders":
            from ..repository.reminders.operations import do_delete_reminder

            title = entry.lookup_key
            content = entry.content

            def on_delete(name=entry.lookup_key) -> None:
                do_delete_reminder(self.ctx, name)
                self._refresh_memory_panel()
        else:
            title = entry.title
            content = entry.content

        self.push_screen(MemoryDetailModal(title, content, on_delete=on_delete))

    def _accept_input_completion(self) -> None:
        input_widget = self.query_one("#chat-input", Input)
        suggestion = getattr(input_widget, "_suggestion", "")
        if suggestion and input_widget.cursor_position >= len(input_widget.value):
            input_widget.action_cursor_right()

    def _render_status_bar(self) -> None:
        import contextlib

        from ..core.status import get_background_status

        try:
            model_name = self.ctx.chat_model.name
        except Exception:
            return

        mode_text = (
            "Browse: j/k or arrows move | Tab next | Shift+Tab prev | Enter open | i/a/Esc chat"
            if self._browse_mode
            else "Chat: Esc browse | Tab complete | F2 panel | Ctrl+D exit"
        )
        if self._streaming:
            prefix = f"{self._spinner_chars[self._spinner_index]} {self._status_message}"
        else:
            bg = get_background_status()
            prefix = f"● {model_name}  ⟳ {bg}" if bg else f"● {model_name}"
        with contextlib.suppress(Exception):
            self.query_one("#status-bar", Label).update(f"{prefix}  |  {mode_text}")


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
        show_memory_panel=params.get("show_memory_panel", True),
    )


def main() -> None:
    from ..core.logging import setup_file_logging
    from ..core.session import init_elroy_session

    setup_file_logging()
    app = make_app()
    with init_elroy_session(app.ctx, app.io, check_db_migration=True, should_onboard_interactive=False):
        app.run()


if __name__ == "__main__":
    main()
