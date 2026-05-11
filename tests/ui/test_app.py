from datetime import timedelta
from threading import Event

import pytest
from rich.text import Text
from sqlmodel import desc, select
from textual import events
from textual.command import CommandPalette
from textual.widgets import Input, Label, ListItem, ListView, RichLog, Tabs

from elroy.core.ctx import ElroyConfig
from elroy.core.session import build_elroy_session, invoke_with_config, open_turn_context
from elroy.core.sidebar_models import SidebarBuilder, SidebarEntry, SidebarEntryRef, SidebarState
from elroy.db.db_models import AgendaItem
from elroy.io.formatters.rich_formatter import RichFormatter
from elroy.repository.context_messages.tools import add_memory_to_current_context
from elroy.repository.memories.tools import create_memory
from elroy.repository.tasks.factory import build_task_mutation_orchestrator
from elroy.repository.user.queries import get_assistant_name
from elroy.repository.user.session import build_user_runtime, build_user_session
from elroy.tools.session import DEFAULT_RESTART_RESUME_PROMPT
from elroy.ui.app import AppRestartRequest, ChatInput, DetailModal, ElroyApp
from elroy.ui.forms import CommandFormScreen
from elroy.ui.session import SessionController
from elroy.utils.clock import utc_now


class HarnessElroyApp(ElroyApp):
    def on_mount(self) -> None:
        self.query_one("#chat-input", ChatInput).focus()
        self._stop_spinner()
        self._load_sidebar_state()
        if self.restart_resume_message:
            self._run_stream(self.session_controller.restart_stream(self.restart_resume_message))

    def _refresh_sidebar_data(self) -> None:
        self._load_sidebar_state()

    def _load_sidebar_state(self) -> None:
        state = SidebarBuilder(self.ctx, self.session).build_sidebar_state()
        self._panel_entries = {"memories": state.memories, "agenda": state.agenda}
        self._chat_suggestions = state.completions
        self._render_sidebar_lists()


def _make_app(ctx: ElroyConfig, rich_formatter: RichFormatter) -> HarnessElroyApp:
    return HarnessElroyApp(
        ctx=ctx,
        session=build_elroy_session(ctx),
        formatter=rich_formatter,
        enable_greeting=False,
        show_internal_thought=False,
    )


def _label_text(label: Label) -> str:
    renderable = label.render()
    if isinstance(renderable, Text):
        return renderable.plain
    return str(renderable)


def _current_list_view(app: ElroyApp) -> ListView:
    return app._current_sidebar_list()


def _sidebar_titles(app: ElroyApp) -> list[str]:
    list_view = _current_list_view(app)
    items = [child for child in list_view.children if isinstance(child, ListItem)]
    return [_label_text(item.query_one(Label)) for item in items]


def _highlighted_indices(app: ElroyApp) -> list[int]:
    list_view = _current_list_view(app)
    items = [child for child in list_view.children if isinstance(child, ListItem)]
    return [index for index, item in enumerate(items) if item.highlighted]


def _history_text(app: ElroyApp) -> str:
    log = app.query_one("#history-log", RichLog)
    return "\n".join(strip.text for strip in log.lines)


def _status_text(app: ElroyApp) -> str:
    return _label_text(app.query_one("#status-bar", Label))


def _binding_description(app: ElroyApp, key: str) -> str:
    return app.active_bindings[key].binding.description


@pytest.mark.asyncio
async def test_tui_cycles_between_chat_history_and_sidebar_sections(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    create_memory(ctx, "Travel preference", "User likes window seats on long flights.")
    invoke_with_config(add_memory_to_current_context, ctx, memory_name="Travel preference")
    with open_turn_context(ctx) as turn:
        task_mutation_orchestrator = build_task_mutation_orchestrator(turn)
        task_mutation_orchestrator.create_task("Drop off parents at airport", "Drop off parents at airport\nBring snacks.")
        task_mutation_orchestrator.create_task(
            "Pay electricity bill",
            "Pay electricity bill before the cutoff date.",
            trigger_datetime=utc_now() - timedelta(minutes=5),
            allow_past_trigger=True,
        )

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.query_one("#chat-input", ChatInput).has_focus
        assert _sidebar_titles(app) == ["Travel preference"]
        assert app.query_one("#sidebar-tabs", Tabs).active == "memories-tab"

        app.action_focus_memories()
        await pilot.pause()

        assert app._browse_mode is True
        assert app._browse_target == "sidebar"
        assert _current_list_view(app).has_focus

        await pilot.press("g")
        await pilot.pause()

        titles = _sidebar_titles(app)
        assert "Drop off parents at airport" in titles
        assert any(title.startswith("Pay electricity bill [") and title.endswith("(Due)") for title in titles)
        assert app.query_one("#sidebar-tabs", Tabs).active == "agenda-tab"

        await pilot.press("tab")
        await pilot.pause()

        assert app._browse_target == "history"
        assert app.query_one("#history-log", RichLog).has_focus

        await pilot.press("tab")
        await pilot.pause()

        assert app._browse_target == "sidebar"
        assert _current_list_view(app).has_focus


@pytest.mark.asyncio
async def test_tui_initial_memory_highlight_matches_first_selected_item(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    create_memory(ctx, "Travel preference", "User likes window seats on long flights.")
    invoke_with_config(add_memory_to_current_context, ctx, memory_name="Travel preference")

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_toggle_browse()
        await pilot.pause()

        list_view = _current_list_view(app)
        assert list_view.index == 0
        assert _highlighted_indices(app) == [0]


@pytest.mark.asyncio
async def test_tui_ctrl_d_exits_even_when_chat_input_has_focus(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.query_one("#chat-input", ChatInput).has_focus
        assert app.is_running is True

        await pilot.press("ctrl+d")
        await pilot.pause()

        assert app.is_running is False


@pytest.mark.asyncio
async def test_tui_multiline_paste_is_flattened_in_chat_input(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        input_widget = app.query_one("#chat-input", ChatInput)
        await input_widget._on_paste(events.Paste("---\ntitle: note\n---\nhello world"))

        assert input_widget.value == "--- title: note --- hello world"


@pytest.mark.asyncio
async def test_tui_chat_input_grows_for_wrapped_text(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)
    async with app.run_test(size=(50, 20)) as pilot:
        await pilot.pause()

        input_widget = app.query_one("#chat-input", ChatInput)
        initial_height = input_widget.size.height
        input_widget.value = "This is a long message that should wrap in the composer instead of scrolling horizontally off screen."
        await pilot.pause()

        assert input_widget.size.height > initial_height


@pytest.mark.asyncio
async def test_tui_renders_existing_context_messages_on_startup(george_ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(george_ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        history = _history_text(app)
        assert "You: Hello! My name is George." in history
        assert "Hello George! It's nice to meet you." in history
        assert "The user has begun the conversation" not in history


@pytest.mark.asyncio
async def test_tui_does_not_render_synthetic_startup_user_message_on_empty_session(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    ctx.chat_model.ensure_alternating_roles = True
    app = _make_app(ctx, rich_formatter)

    async with app.run_test() as pilot:
        await pilot.pause()

        history = _history_text(app)
        assert "The user has begun the conversation" not in history


@pytest.mark.asyncio
async def test_tui_runs_restart_prompt_on_startup(ctx: ElroyConfig, rich_formatter: RichFormatter, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_restart_stream(self, prompt: str):
        captured["prompt"] = prompt
        yield "Restarted successfully. Ready to continue."

    monkeypatch.setattr("elroy.ui.session.SessionController.restart_stream", fake_restart_stream)

    app = ElroyApp(
        ctx=ctx,
        session=build_elroy_session(ctx),
        formatter=rich_formatter,
        enable_greeting=False,
        show_internal_thought=False,
        restart_resume_message="Restarted successfully. Ready to continue.",
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        assert captured["prompt"] == "Restarted successfully. Ready to continue."
        assert "Restarted successfully. Ready to continue." in _history_text(app)


def test_restart_stream_uses_non_persisted_input(ctx: ElroyConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_process_message(**kwargs):
        captured.update(kwargs)
        yield "done"

    monkeypatch.setattr("elroy.messenger.messenger.process_message", fake_process_message)

    stream = SessionController(ctx, build_elroy_session(ctx)).restart_stream("Restarted successfully. Ready to continue.")
    assert list(stream) == ["done"]
    assert captured["msg"] == "Restarted successfully. Ready to continue."
    assert captured["persist_input_message"] is False


@pytest.mark.asyncio
async def test_tui_agenda_keyboard_navigation_works_after_section_switch(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    with open_turn_context(ctx) as turn:
        task_mutation_orchestrator = build_task_mutation_orchestrator(turn)
        task_mutation_orchestrator.create_task("Job search", "Job search\nReach out to three contacts.")
        task_mutation_orchestrator.create_task("Drop off parents at airport", "Drop off parents at airport\nBring snacks.")
        task_mutation_orchestrator.create_task("Buy groceries", "Buy groceries\nMilk, eggs, bread.")

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_focus_agenda()
        await pilot.pause()

        list_view = _current_list_view(app)
        assert list_view.index == 0
        assert _highlighted_indices(app) == [0]

        await pilot.press("j")
        await pilot.pause()
        assert list_view.index == 1
        assert _highlighted_indices(app) == [1]

        await pilot.press("down")
        await pilot.pause()
        assert list_view.index == 2
        assert _highlighted_indices(app) == [2]

        await pilot.press("k")
        await pilot.pause()
        assert list_view.index == 1
        assert _highlighted_indices(app) == [1]

        await pilot.press("up")
        await pilot.pause()
        assert list_view.index == 0
        assert _highlighted_indices(app) == [0]


@pytest.mark.asyncio
async def test_tui_ctrl_m_focuses_memories_sidebar(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    create_memory(ctx, "Travel preference", "User likes window seats on long flights.")
    invoke_with_config(add_memory_to_current_context, ctx, memory_name="Travel preference")

    with open_turn_context(ctx) as turn:
        task_mutation_orchestrator = build_task_mutation_orchestrator(turn)
        task_mutation_orchestrator.create_task("Job search", "Job search\nReach out to three contacts.")

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.query_one("#chat-input", ChatInput).has_focus
        assert _binding_description(app, "ctrl+m") == "Memories"

        app.action_focus_agenda()
        await pilot.pause()

        assert app.query_one("#sidebar-tabs", Tabs).active == "agenda-tab"

        app.action_toggle_memory()
        await pilot.pause()

        assert app._browse_mode is True
        assert app._browse_target == "sidebar"
        assert _current_list_view(app).has_focus
        assert app.query_one("#sidebar-tabs", Tabs).active == "memories-tab"
        assert _binding_description(app, "ctrl+m") == "Memories"


@pytest.mark.asyncio
async def test_tui_ctrl_a_binding_targets_agenda(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert _binding_description(app, "ctrl+a") == "Agenda"


@pytest.mark.asyncio
async def test_tui_focus_agenda_enters_sidebar_and_supports_arrow_navigation(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    with open_turn_context(ctx) as turn:
        task_mutation_orchestrator = build_task_mutation_orchestrator(turn)
        task_mutation_orchestrator.create_task("Job search", "Job search\nReach out to three contacts.")
        task_mutation_orchestrator.create_task("Drop off parents at airport", "Drop off parents at airport\nBring snacks.")

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        app.action_focus_agenda()
        await pilot.pause()

        list_view = _current_list_view(app)
        assert app._browse_mode is True
        assert app._browse_target == "sidebar"
        assert app.query_one("#sidebar-tabs", Tabs).active == "agenda-tab"
        assert list_view.has_focus
        assert list_view.index == 0

        await pilot.press("down")
        await pilot.pause()

        assert list_view.index == 1
        assert _highlighted_indices(app) == [1]


@pytest.mark.asyncio
async def test_tui_agenda_modal_marks_item_complete(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    with open_turn_context(ctx) as turn:
        build_task_mutation_orchestrator(turn).create_task("Job search", "Job search\nReach out to three contacts.")

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_focus_agenda()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, DetailModal)
        footer = app.screen.query_one("#memory-detail-footer", Label)
        assert _label_text(footer) == "C: complete  |  Escape/Enter/Q: close"

        await pilot.press("c")
        await pilot.pause()

        with open_turn_context(ctx) as turn:
            task = (
                build_user_session(turn)
                .db.exec(select(AgendaItem).where(AgendaItem.name == "Job search").order_by(desc(AgendaItem.created_at)))
                .first()
            )
        assert task is not None
        assert task.status == "completed"
        assert "Job search" not in _sidebar_titles(app)


@pytest.mark.asyncio
async def test_tui_open_agenda_select_item_and_mark_complete(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    with open_turn_context(ctx) as turn:
        task_mutation_orchestrator = build_task_mutation_orchestrator(turn)
        task_mutation_orchestrator.create_task("Job search", "Job search\nReach out to three contacts.")
        task_mutation_orchestrator.create_task("Drop off parents at airport", "Drop off parents at airport\nBring snacks.")

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        app.action_focus_agenda()
        await pilot.pause()
        await pilot.press("down", "enter")
        await pilot.pause()

        assert isinstance(app.screen, DetailModal)
        assert _label_text(app.screen.query_one("#memory-detail-title", Label)) == "Drop off parents at airport"

        await pilot.press("c")
        await pilot.pause()

        with open_turn_context(ctx) as turn:
            task = (
                build_user_session(turn)
                .db.exec(select(AgendaItem).where(AgendaItem.name == "Drop off parents at airport").order_by(desc(AgendaItem.created_at)))
                .first()
            )
        assert task is not None
        assert task.status == "completed"
        assert "Drop off parents at airport" not in _sidebar_titles(app)


@pytest.mark.asyncio
async def test_tui_due_item_modal_confirms_delete(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    with open_turn_context(ctx) as turn:
        build_task_mutation_orchestrator(turn).create_task(
            "Pay rent",
            "Pay rent before the first of the month.",
            trigger_datetime=utc_now() - timedelta(minutes=5),
            allow_past_trigger=True,
        )

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_focus_agenda()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, DetailModal)
        footer = app.screen.query_one("#memory-detail-footer", Label)
        assert _label_text(footer) == "C: complete  |  D: delete  |  Escape/Enter/Q: close"

        await pilot.press("d")
        await pilot.pause()
        assert _label_text(footer) == "Press D again to confirm deletion, any other key to cancel"

        await pilot.press("d")
        await pilot.pause()

        with open_turn_context(ctx) as turn:
            task = (
                build_user_session(turn)
                .db.exec(select(AgendaItem).where(AgendaItem.name == "Pay rent").order_by(desc(AgendaItem.created_at)))
                .first()
            )
        assert task is not None
        assert task.status == "deleted"
        assert all("Pay rent" not in title for title in _sidebar_titles(app))


@pytest.mark.asyncio
async def test_tui_system_commands_include_palette_actions(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        commands = list(app.get_system_commands(app.screen))
        titles = {command.title for command in commands}
        assert "Focus Memories" in titles
        assert "Focus Agenda" in titles
        assert "Refresh System Instructions" in titles
        assert "Reset Messages" in titles


@pytest.mark.asyncio
async def test_tui_status_bar_does_not_duplicate_command_palette_hint(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        status = _status_text(app)
        assert "Ctrl+P" not in status
        assert "commands" not in status.lower()


@pytest.mark.asyncio
async def test_tui_slash_command_with_missing_args_opens_modal_form(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        input_widget = app.query_one("#chat-input", ChatInput)
        input_widget.value = "/set_assistant_name"
        app._submit_chat_input()
        await pilot.pause()

        assert isinstance(app.screen, CommandFormScreen)
        field = app.screen.query_one("#input-assistant_name", Input)
        field.value = "Jarvis"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        with open_turn_context(ctx) as turn:
            assert get_assistant_name(build_user_session(turn), build_user_runtime(turn)) == "Jarvis"


@pytest.mark.asyncio
async def test_tui_enter_submits_chat_input(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        input_widget = app.query_one("#chat-input", ChatInput)
        input_widget.value = "/set_assistant_name Jarvis"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        with open_turn_context(ctx) as turn:
            assert get_assistant_name(build_user_session(turn), build_user_runtime(turn)) == "Jarvis"
        assert input_widget.value == ""


@pytest.mark.asyncio
async def test_tui_chat_input_stays_editable_while_chat_stream_runs(
    ctx: ElroyConfig, rich_formatter: RichFormatter, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Event()
    release = Event()

    def fake_process_message(*, role, ctx, session, msg, enable_tools=True):
        del role, ctx, session, msg, enable_tools
        started.set()
        release.wait(timeout=2)
        yield "done"

    monkeypatch.setattr("elroy.messenger.messenger.process_message", fake_process_message)

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        input_widget = app.query_one("#chat-input", ChatInput)
        app._process_chat_message("hello")

        for _ in range(20):
            await pilot.pause()
            if started.is_set() and "chat-stream" in app._active_worker_groups:
                break

        assert started.is_set()
        assert "chat-stream" in app._active_worker_groups

        await pilot.press("d", "r", "a", "f", "t")
        await pilot.pause()

        assert input_widget.value == "draft"
        assert input_widget.disabled is False
        assert input_widget.has_focus

        await pilot.press("enter")
        await pilot.pause()

        assert input_widget.value == "draft"
        assert "Wait for the current task to finish before sending another message." in _history_text(app)

        release.set()
        await pilot.pause()
        await pilot.pause()


@pytest.mark.asyncio
async def test_tui_cancel_stream_preserves_draft_text(
    ctx: ElroyConfig, rich_formatter: RichFormatter, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Event()
    release = Event()

    def fake_process_message(*, role, ctx, session, msg, enable_tools=True):
        del role, ctx, session, msg, enable_tools
        started.set()
        release.wait(timeout=2)
        yield "done"

    monkeypatch.setattr("elroy.messenger.messenger.process_message", fake_process_message)

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        input_widget = app.query_one("#chat-input", ChatInput)
        app._process_chat_message("hello")

        for _ in range(20):
            await pilot.pause()
            if started.is_set() and "chat-stream" in app._active_worker_groups:
                break

        assert started.is_set()

        await pilot.press("d", "r", "a", "f", "t")
        await pilot.pause()
        assert input_widget.value == "draft"

        app.action_cancel_stream()
        release.set()
        await pilot.pause()
        await pilot.pause()

        assert input_widget.value == "draft"
        assert "chat-stream" not in app._active_worker_groups


@pytest.mark.asyncio
async def test_tui_chat_input_stays_editable_while_command_runs(
    ctx: ElroyConfig, rich_formatter: RichFormatter, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Event()
    release = Event()

    def fake_run_tool_command(self, spec, values):
        del self, spec, values

        def stream():
            started.set()
            release.wait(timeout=2)
            yield "done"

        return stream()

    monkeypatch.setattr("elroy.ui.session.SessionController.run_tool_command", fake_run_tool_command)

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        input_widget = app.query_one("#chat-input", ChatInput)
        app._execute_tool_command("refresh_system_instructions", {}, "palette")

        for _ in range(20):
            await pilot.pause()
            if started.is_set() and "command-action" in app._active_worker_groups:
                break

        assert started.is_set()
        assert "command-action" in app._active_worker_groups

        await pilot.press("d", "r", "a", "f", "t")
        await pilot.pause()

        assert input_widget.value == "draft"
        assert input_widget.disabled is False
        assert input_widget.has_focus

        await pilot.press("enter")
        await pilot.pause()

        assert input_widget.value == "draft"
        assert "Wait for the current task to finish before sending another message." in _history_text(app)

        release.set()
        await pilot.pause()
        await pilot.pause()


@pytest.mark.asyncio
async def test_tui_consumes_restart_request_and_exits_with_restart_result(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)

    async with app.run_test() as pilot:
        await pilot.pause()

        app.session.restart_state.request("Restarted successfully. Ready to continue.")
        app._finalize_turn_ui_state()
        await pilot.pause()

        assert app.is_running is False
        assert app.return_value == AppRestartRequest("Restarted successfully. Ready to continue.")


@pytest.mark.asyncio
async def test_tui_restart_session_command_exits_with_restart_result(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)

    async with app.run_test() as pilot:
        await pilot.pause()

        app._execute_tool_command("restart_session", {}, "palette")

        for _ in range(20):
            await pilot.pause()
            if app.is_running is False:
                break

        assert app.is_running is False
        assert app.return_value == AppRestartRequest(DEFAULT_RESTART_RESUME_PROMPT)


@pytest.mark.asyncio
async def test_tui_streaming_draft_survives_browse_mode_switches(
    ctx: ElroyConfig, rich_formatter: RichFormatter, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Event()
    release = Event()

    def fake_process_message(*, role, ctx, session, msg, enable_tools=True):
        del role, ctx, session, msg, enable_tools
        started.set()
        release.wait(timeout=2)
        yield "done"

    monkeypatch.setattr("elroy.messenger.messenger.process_message", fake_process_message)

    with open_turn_context(ctx) as turn:
        task_mutation_orchestrator = build_task_mutation_orchestrator(turn)
        task_mutation_orchestrator.create_task("Job search", "Job search\nReach out to three contacts.")

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        input_widget = app.query_one("#chat-input", ChatInput)
        app._process_chat_message("hello")

        for _ in range(20):
            await pilot.pause()
            if started.is_set() and "chat-stream" in app._active_worker_groups:
                break

        await pilot.press("d", "r", "a", "f", "t")
        await pilot.pause()
        assert input_widget.value == "draft"

        app.action_focus_memories()
        await pilot.pause()
        assert app._browse_mode is True
        assert input_widget.value == "draft"

        await pilot.press("g")
        await pilot.pause()
        assert app.query_one("#sidebar-tabs", Tabs).active == "agenda-tab"
        assert input_widget.value == "draft"

        app._focus_chat_input()
        await pilot.pause()
        assert app._browse_mode is False
        assert input_widget.has_focus
        assert input_widget.value == "draft"

        release.set()
        await pilot.pause()
        await pilot.pause()


@pytest.mark.asyncio
async def test_tui_streaming_draft_survives_sidebar_and_status_updates(
    ctx: ElroyConfig, rich_formatter: RichFormatter, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Event()
    release = Event()

    def fake_process_message(*, role, ctx, session, msg, enable_tools=True):
        del role, ctx, session, msg, enable_tools
        started.set()
        release.wait(timeout=2)
        yield "done"

    monkeypatch.setattr("elroy.messenger.messenger.process_message", fake_process_message)

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        input_widget = app.query_one("#chat-input", ChatInput)
        app._process_chat_message("hello")

        for _ in range(20):
            await pilot.pause()
            if started.is_set() and "chat-stream" in app._active_worker_groups:
                break

        await pilot.press("d", "r", "a", "f", "t")
        await pilot.pause()
        assert input_widget.value == "draft"

        app._apply_sidebar_state(
            SidebarState(
                memories=[
                    SidebarEntry(
                        title="Trip note",
                        ref=SidebarEntryRef(kind="memory", key="Trip note", source_type="Memory"),
                        content="",
                    )
                ],
                agenda=[SidebarEntry(title="Call mom", ref=SidebarEntryRef(kind="agenda", key="Call mom"), content="Call mom tonight")],
                completions=["Trip note"],
            )
        )
        await pilot.pause()

        assert input_widget.value == "draft"
        assert _sidebar_titles(app) == ["Trip note"]

        app._set_status_message("loading context...")
        await pilot.pause()

        assert input_widget.value == "draft"
        assert "loading context..." in _status_text(app)

        release.set()
        await pilot.pause()
        await pilot.pause()


@pytest.mark.asyncio
async def test_tui_ctrl_p_opens_command_palette_from_chat_input(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.query_one("#chat-input", ChatInput).has_focus

        await pilot.press("ctrl+p")
        await pilot.pause()

        assert isinstance(app.screen, CommandPalette)


@pytest.mark.asyncio
async def test_tui_launch_tool_command_opens_modal_form(ctx: ElroyConfig, rich_formatter: RichFormatter) -> None:
    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        app.launch_tool_command("create_memory")
        await pilot.pause()

        assert isinstance(app.screen, CommandFormScreen)
        name_field = app.screen.query_one("#input-name", Input)
        text_field = app.screen.query_one("#input-text", Input)
        name_field.value = "Trip note"
        text_field.value = "User prefers aisle seats."
        text_field.focus()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        assert "Trip note" in _sidebar_titles(app)
