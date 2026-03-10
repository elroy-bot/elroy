"""Textual TUI for Elroy chat interface."""

import re
from collections.abc import AsyncIterator, Iterator
from datetime import timedelta
from pathlib import Path
from typing import ClassVar, cast

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.suggester import SuggestFromList
from textual.widgets import Input, Label, ListItem, ListView, RichLog, Static

from ..config.paths import get_prompt_history_path
from ..core.constants import EXIT, USER
from ..core.ctx import ElroyContext
from ..core.logging import get_logger
from ..io.base import ElroyIO
from ..io.completions import build_completions, get_memory_panel_titles
from ..io.formatters.rich_formatter import RichFormatter
from ..io.textual_io import TextualIO

logger = get_logger()


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
        background: $panel;
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
        self._input_history: list[str] = []
        self._history_index = -1
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
                yield Label("In-Context Memories", id="memory-title")
                yield ListView(id="memory-list")
        yield Input(placeholder="> ", id="chat-input")
        yield Label("", id="status-bar")

    def on_mount(self) -> None:
        if not self._memory_panel_visible:
            self.query_one("#memory-panel").add_class("hidden")

        self.query_one("#chat-input").focus()

        from ..repository.user.queries import get_assistant_name

        self.title = get_assistant_name(self.ctx)
        self._update_status_bar()
        self.set_interval(5.0, self._update_status_bar)
        self._start_session()

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
        self._streaming = True
        self.call_from_thread(self._set_input_disabled, True)
        self.call_from_thread(self._update_status_bar)
        try:
            for item in stream:
                self.io.print(item, end="")
        finally:
            self.call_from_thread(self._flush_thought_buffer)
            self.call_from_thread(self._flush_streaming_buffer)
            self._streaming = False
            self.call_from_thread(self._set_input_disabled, False)
            self.call_from_thread(self._update_status_bar)

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
        if not input_widget.has_focus:
            return

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
        else:
            panel.add_class("hidden")

    # ── periodic updates ──────────────────────────────────────────────────────

    @work(thread=True)
    def _refresh_memory_panel(self) -> None:
        try:
            titles = get_memory_panel_titles(self.ctx)
            list_view = self.query_one("#memory-list", ListView)
            self.call_from_thread(list_view.clear)
            for title in titles[:15]:
                self.call_from_thread(list_view.append, ListItem(Label(title)))
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

    def _update_status_bar(self) -> None:
        try:
            model_name = self.ctx.chat_model.name
            status = "⏳ streaming..." if self._streaming else f"● {model_name}"
            self.query_one("#status-bar", Label).update(status)
        except Exception:
            pass


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
    from ..core.session import init_elroy_session

    app = make_app()
    with init_elroy_session(app.ctx, app.io, check_db_migration=True, should_onboard_interactive=False):
        app.run()


if __name__ == "__main__":
    main()
