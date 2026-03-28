"""Textual TUI for Elroy chat interface."""

import re
from collections.abc import AsyncIterator, Callable, Iterator
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
from textual.widgets import Input, Label, ListItem, ListView, RichLog, Static, Tab, Tabs

from ..config.paths import get_prompt_history_path
from ..core.constants import EXIT, USER
from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..io.base import ElroyIO
from ..io.completions import build_completions
from ..io.formatters.rich_formatter import RichFormatter
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

    #buffer-tabs {
        height: auto;
        dock: top;
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

    #hints-bar {
        height: 1;
        background: $boost;
        color: $text-disabled;
        padding: 0 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+d", "quit", "Exit"),
        Binding("ctrl+c", "cancel_stream", "Cancel", show=False),
        Binding("f2", "toggle_memory", "Toggle Panel"),
        Binding("escape", "toggle_browse_mode", "Browse", show=False),
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
        self._right_panel_mode = "memories"  # "memories", "reminders", "agenda"
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
                yield Tabs(
                    Tab("Memories", id="tab-memories"),
                    Tab("Reminders", id="tab-reminders"),
                    Tab("Agenda", id="tab-agenda"),
                    id="buffer-tabs",
                )
                yield ListView(id="memory-list")
        yield Input(placeholder="> ", id="chat-input")
        yield Label("", id="status-bar")
        yield Label("", id="hints-bar")

    def on_mount(self) -> None:
        if not self._memory_panel_visible:
            self.query_one("#memory-panel").add_class("hidden")

        self.query_one("#chat-input").focus()

        from ..repository.user.queries import get_assistant_name

        self.title = get_assistant_name(self.ctx)
        self._stop_spinner()  # initialise status bar with model name
        self._update_hints()
        self._bg_status_handle = self.set_interval(1.0, self._tick_background_status)
        self._start_session()

    # ── buffer tabs ───────────────────────────────────────────────────────────

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        if event.tabs.id != "buffer-tabs":
            return
        if event.tab is None:
            return
        tab_id = event.tab.id
        if tab_id == "tab-memories":
            self._right_panel_mode = "memories"
            self._refresh_memory_panel()
        elif tab_id == "tab-reminders":
            self._right_panel_mode = "reminders"
            self._refresh_reminders_panel()
        elif tab_id == "tab-agenda":
            self._right_panel_mode = "agenda"
            self._refresh_agenda_panel()
        self._update_hints()

    def _show_panel(self) -> None:
        """Ensure the right panel is visible."""
        panel = self.query_one("#memory-panel")
        if not self._memory_panel_visible:
            self._memory_panel_visible = True
            panel.remove_class("hidden")

    # ── list selection ────────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "memory-list":
            return

        type_key = event.item.name
        if not type_key:
            return

        if type_key.startswith("reminder:"):
            reminder_name = type_key[len("reminder:"):]
            self._open_reminder_detail(reminder_name)
        elif type_key.startswith("agenda:"):
            item_stem = type_key[len("agenda:"):]
            self._open_agenda_detail(item_stem)
        elif ": " in type_key:
            # Memory
            from ..db.db_models import EmbeddableSqlModel
            from ..repository.memories.operations import mark_inactive
            from ..repository.memories.queries import db_get_memory_source_by_name

            source_type, name = type_key.split(": ", 1)
            source = db_get_memory_source_by_name(self.ctx, source_type, name)
            if source:
                on_delete = None
                if isinstance(source, EmbeddableSqlModel):

                    def on_delete(s=source) -> None:
                        mark_inactive(self.ctx, s)
                        self._refresh_memory_panel()

                self.push_screen(MemoryDetailModal(name, source.to_fact(), on_delete=on_delete))

    def _open_reminder_detail(self, reminder_name: str) -> None:
        from ..repository.reminders.operations import do_delete_reminder
        from ..repository.reminders.queries import get_db_reminder_by_name
        from ..utils.clock import db_time_to_local

        reminder = get_db_reminder_by_name(self.ctx, reminder_name)
        if not reminder:
            return

        parts = [f"Text: {reminder.text}"]
        if reminder.trigger_datetime:
            dt = db_time_to_local(reminder.trigger_datetime)
            parts.append(f"\nDue: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        if reminder.reminder_context:
            parts.append(f"\nContext: {reminder.reminder_context}")
        parts.append(f"\nCreated: {db_time_to_local(reminder.created_at).strftime('%Y-%m-%d %H:%M:%S')}")

        def on_delete() -> None:
            do_delete_reminder(self.ctx, reminder_name)
            self._refresh_reminders_panel()

        self.push_screen(MemoryDetailModal(reminder_name, "\n".join(parts), on_delete=on_delete))

    def _open_agenda_detail(self, item_stem: str) -> None:
        from ..config.paths import get_agenda_dir
        from ..repository.agenda.file_storage import find_matching_agenda_item

        try:
            agenda_dir = get_agenda_dir()
            path = find_matching_agenda_item(agenda_dir, item_stem)
            content = path.read_text()
            self.push_screen(MemoryDetailModal(item_stem, content))
        except Exception:
            logger.debug("Failed to open agenda detail for %s", item_stem, exc_info=True)

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

        self._refresh_right_panel()
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
            input_widget.focus()
            self._update_hints()

    def _update_hints(self) -> None:
        """Refresh the hints bar with context-sensitive keybinding help."""
        import contextlib

        list_view = self.query_one("#memory-list", ListView)
        if list_view.has_focus:
            buf = self._right_panel_mode.capitalize()
            text = f"[{buf}]  ↑↓/jk: move  ·  Tab/Shift+Tab: cycle buffers  ·  Enter: open  ·  i/a: back to chat  ·  Esc: back"
        else:
            text = "Esc: browse panel  ·  F2: toggle panel  ·  Ctrl+D: exit"
        with contextlib.suppress(Exception):
            self.query_one("#hints-bar", Label).update(text)

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
        list_view = self.query_one("#memory-list", ListView)

        if input_widget.has_focus:
            if event.key == "up":
                if self._input_history and self._history_index < len(self._input_history) - 1:
                    self._history_index += 1
                    input_widget.value = self._input_history[self._history_index]
                    input_widget.cursor_position = len(input_widget.value)
                event.prevent_default()
            elif event.key == "down":
                if self._history_index > 0:
                    self._history_index -= 1
                    input_widget.value = self._input_history[self._history_index]
                    input_widget.cursor_position = len(input_widget.value)
                elif self._history_index == 0:
                    self._history_index = -1
                    input_widget.value = ""
                event.prevent_default()
        elif list_view.has_focus:
            if event.key in ("i", "a"):
                # Insert/append → return to chat input (vim-like)
                input_widget.focus()
                self._update_hints()
                event.prevent_default()
                event.stop()
            elif event.key == "j":
                list_view.action_cursor_down()
                event.prevent_default()
                event.stop()
            elif event.key == "k":
                list_view.action_cursor_up()
                event.prevent_default()
                event.stop()
            elif event.key == "tab":
                self._cycle_buffer(1)
                self.call_later(self._update_hints)
                event.prevent_default()
                event.stop()
            elif event.key == "shift+tab":
                self._cycle_buffer(-1)
                self.call_later(self._update_hints)
                event.prevent_default()
                event.stop()

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
            self._refresh_right_panel()
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
        else:
            panel.add_class("hidden")

    def action_toggle_browse_mode(self) -> None:
        """Escape: toggle between chat input and right-panel browse mode."""
        input_widget = self.query_one("#chat-input", Input)
        list_view = self.query_one("#memory-list", ListView)
        if list_view.has_focus:
            input_widget.focus()
        else:
            self._show_panel()
            list_view.focus()
        self.call_later(self._update_hints)

    def _cycle_buffer(self, direction: int) -> None:
        """Cycle through Memories → Reminders → Agenda (Tab/Shift+Tab in browse mode)."""
        modes = ["memories", "reminders", "agenda"]
        tab_ids = ["tab-memories", "tab-reminders", "tab-agenda"]
        idx = modes.index(self._right_panel_mode)
        self.query_one("#buffer-tabs", Tabs).active = tab_ids[(idx + direction) % len(modes)]

    # ── panel refresh ─────────────────────────────────────────────────────────

    def _refresh_right_panel(self) -> None:
        """Refresh whichever buffer is currently active."""
        if self._right_panel_mode == "memories":
            self._refresh_memory_panel()
        elif self._right_panel_mode == "reminders":
            self._refresh_reminders_panel()
        elif self._right_panel_mode == "agenda":
            self._refresh_agenda_panel()

    @work(thread=True)
    def _refresh_memory_panel(self) -> None:
        try:
            from ..repository.context_messages.queries import get_context_messages
            from ..repository.memories.queries import get_active_memories
            from ..repository.recall.queries import is_in_context

            context_messages = list(get_context_messages(self.ctx))
            memories = get_active_memories(self.ctx)
            in_context_names = {m.get_name() for m in memories if is_in_context(context_messages, m)}

            list_view = self.query_one("#memory-list", ListView)
            self.call_from_thread(list_view.clear)
            for memory in memories:
                name = memory.get_name()
                marker = "● " if name in in_context_names else "  "
                display = Text(f"{marker}{name}", no_wrap=True, overflow="ellipsis")
                type_key = f"Memory: {name}"
                self.call_from_thread(list_view.append, ListItem(Label(display), name=type_key))
        except Exception:
            logger.debug("Failed to refresh memory panel", exc_info=True)

    @work(thread=True)
    def _refresh_reminders_panel(self) -> None:
        try:
            from ..repository.reminders.queries import get_active_reminders
            from ..utils.clock import db_time_to_local

            reminders = get_active_reminders(self.ctx)
            list_view = self.query_one("#memory-list", ListView)
            self.call_from_thread(list_view.clear)
            for r in reminders:
                if r.trigger_datetime:
                    dt = db_time_to_local(r.trigger_datetime)
                    raw = f"{r.name} [{dt.strftime('%m/%d %H:%M')}]"
                elif r.reminder_context:
                    raw = f"{r.name} [ctx]"
                else:
                    raw = r.name
                display = Text(raw, no_wrap=True, overflow="ellipsis")
                self.call_from_thread(list_view.append, ListItem(Label(display), name=f"reminder:{r.name}"))
        except Exception:
            logger.debug("Failed to refresh reminders panel", exc_info=True)

    @work(thread=True)
    def _refresh_agenda_panel(self) -> None:
        try:
            from datetime import date

            from ..config.paths import get_agenda_dir
            from ..repository.agenda.file_storage import get_checklist
            from ..repository.agenda.file_storage import list_agenda_items as list_agenda_items_from_dir

            agenda_dir = get_agenda_dir()
            items = list_agenda_items_from_dir(agenda_dir, for_date=date.today())
            list_view = self.query_one("#memory-list", ListView)
            self.call_from_thread(list_view.clear)
            for path, _fm, _text in items:
                checklist = get_checklist(path)
                if checklist:
                    done = sum(1 for c in checklist if c["completed"])
                    raw = f"{path.stem} [{done}/{len(checklist)}]"
                else:
                    raw = path.stem
                display = Text(raw, no_wrap=True, overflow="ellipsis")
                self.call_from_thread(list_view.append, ListItem(Label(display), name=f"agenda:{path.stem}"))
        except Exception:
            logger.debug("Failed to refresh agenda panel", exc_info=True)

    # ── completions ───────────────────────────────────────────────────────────

    @work(thread=True)
    def _update_completions(self) -> None:
        try:
            suggestions = build_completions(self.ctx)
            input_widget = self.query_one("#chat-input", Input)
            self.call_from_thread(setattr, input_widget, "suggester", SuggestFromList(suggestions, case_sensitive=False))
        except Exception:
            logger.debug("Failed to update completions", exc_info=True)

    # ── spinner / status bar ──────────────────────────────────────────────────

    def _start_spinner(self) -> None:
        self._spinner_index = 0
        self._status_message = "thinking..."
        if self._spinner_handle:
            self._spinner_handle.stop()
        self._spinner_handle = self.set_interval(0.08, self._tick_spinner)

    def _tick_spinner(self) -> None:
        import contextlib

        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_chars)
        with contextlib.suppress(Exception):
            self.query_one("#status-bar", Label).update(f"{self._spinner_chars[self._spinner_index]} {self._status_message}")

    def _update_spinner_text(self) -> None:
        """Immediately refresh the status bar text without advancing the spinner frame."""
        import contextlib

        with contextlib.suppress(Exception):
            spinner_char = self._spinner_chars[self._spinner_index]
            self.query_one("#status-bar", Label).update(f"{spinner_char} {self._status_message}")

    def _stop_spinner(self) -> None:
        if self._spinner_handle:
            self._spinner_handle.stop()
            self._spinner_handle = None
        self._status_message = "thinking..."
        self._update_idle_status()

    def _update_idle_status(self) -> None:
        """Refresh the status bar when not streaming, incorporating background task status."""
        import contextlib

        from ..core.status import get_background_status

        try:
            model_name = self.ctx.chat_model.name
        except Exception:
            return
        bg = get_background_status()
        text = f"● {model_name}  ⟳ {bg}" if bg else f"● {model_name}"
        with contextlib.suppress(Exception):
            self.query_one("#status-bar", Label).update(text)

    def _tick_background_status(self) -> None:
        """Periodically update the idle status bar with background task activity."""
        if not self._streaming:
            self._update_idle_status()


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
