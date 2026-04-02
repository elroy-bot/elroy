from datetime import timedelta

import pytest
from rich.text import Text
from sqlmodel import select
from textual.suggester import SuggestFromList
from textual.widgets import Input, Label, ListItem, ListView, RichLog

from elroy.core.ctx import ElroyContext
from elroy.core.services.sidebar_service import AgendaPresenter
from elroy.db.db_models import AgendaItem
from elroy.io.formatters.rich_formatter import RichFormatter
from elroy.io.textual_app import ElroyApp, MemoryDetailModal
from elroy.repository.context_messages.tools import add_memory_to_current_context
from elroy.repository.memories.tools import create_memory
from elroy.repository.tasks.operations import create_task
from elroy.utils.clock import utc_now


class HarnessElroyApp(ElroyApp):
    def on_mount(self) -> None:
        self.query_one("#chat-input", Input).focus()
        self._stop_spinner()
        self._load_sidebar_state()

    def _refresh_sidebar_data(self) -> None:
        self._load_sidebar_state()

    def _load_sidebar_state(self) -> None:
        state = AgendaPresenter(self.ctx).build_sidebar_state()
        self._panel_entries = {"memories": state.memories, "agenda": state.agenda}
        self._render_sidebar_list()
        input_widget = self.query_one("#chat-input", Input)
        input_widget.suggester = SuggestFromList(state.completions, case_sensitive=False)


def _make_app(ctx: ElroyContext, rich_formatter: RichFormatter) -> HarnessElroyApp:
    return HarnessElroyApp(
        ctx=ctx,
        formatter=rich_formatter,
        enable_greeting=False,
        show_internal_thought=False,
        show_memory_panel=True,
    )


def _label_text(label: Label) -> str:
    renderable = label.render()
    if isinstance(renderable, Text):
        return renderable.plain
    return str(renderable)


def _sidebar_titles(app: ElroyApp) -> list[str]:
    list_view = app.query_one("#sidebar-list", ListView)
    items = [child for child in list_view.children if isinstance(child, ListItem)]
    return [_label_text(item.query_one(Label)) for item in items]


@pytest.mark.asyncio
async def test_tui_cycles_between_chat_history_and_sidebar_sections(ctx: ElroyContext, rich_formatter: RichFormatter) -> None:
    create_memory(ctx, "Travel preference", "User likes window seats on long flights.")
    add_memory_to_current_context(ctx, "Travel preference")
    create_task(ctx, "Drop off parents at airport", "Drop off parents at airport\nBring snacks.")
    create_task(
        ctx,
        "Pay electricity bill",
        "Pay electricity bill before the cutoff date.",
        trigger_datetime=utc_now() - timedelta(minutes=5),
        allow_past_trigger=True,
    )

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.query_one("#chat-input", Input).has_focus
        assert _sidebar_titles(app) == ["Travel preference"]
        assert app.query_one("#memories-title", Label).has_class("active")

        await pilot.press("escape")
        await pilot.pause()

        assert app._browse_mode is True
        assert app._browse_target == "sidebar"
        assert app.query_one("#sidebar-list", ListView).has_focus

        await pilot.press("g")
        await pilot.pause()

        titles = _sidebar_titles(app)
        assert "Drop off parents at airport" in titles
        assert any(title.startswith("Pay electricity bill [") and title.endswith("(Due)") for title in titles)
        assert app.query_one("#agenda-title", Label).has_class("active")
        assert not app.query_one("#memories-title", Label).has_class("active")

        await pilot.press("tab")
        await pilot.pause()

        assert app._browse_target == "history"
        assert app.query_one("#history-log", RichLog).has_focus

        await pilot.press("tab")
        await pilot.pause()

        assert app._browse_target == "sidebar"
        assert app.query_one("#sidebar-list", ListView).has_focus


@pytest.mark.asyncio
async def test_tui_agenda_modal_marks_item_complete(ctx: ElroyContext, rich_formatter: RichFormatter) -> None:
    create_task(ctx, "Job search", "Job search\nReach out to three contacts.")

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape", "g", "enter")
        await pilot.pause()

        assert isinstance(app.screen, MemoryDetailModal)
        footer = app.screen.query_one("#memory-detail-footer", Label)
        assert _label_text(footer) == "C: complete  |  Escape/Enter/Q: close"

        await pilot.press("c")
        await pilot.pause()

        task = ctx.db.exec(select(AgendaItem).where(AgendaItem.name == "Job search")).one()
        assert task.status == "completed"
        assert "Job search" not in _sidebar_titles(app)


@pytest.mark.asyncio
async def test_tui_due_item_modal_confirms_delete(ctx: ElroyContext, rich_formatter: RichFormatter) -> None:
    create_task(
        ctx,
        "Pay rent",
        "Pay rent before the first of the month.",
        trigger_datetime=utc_now() - timedelta(minutes=5),
        allow_past_trigger=True,
    )

    app = _make_app(ctx, rich_formatter)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape", "g", "enter")
        await pilot.pause()

        assert isinstance(app.screen, MemoryDetailModal)
        footer = app.screen.query_one("#memory-detail-footer", Label)
        assert _label_text(footer) == "C: complete  |  D: delete  |  Escape/Enter/Q: close"

        await pilot.press("d")
        await pilot.pause()
        assert _label_text(footer) == "Press D again to confirm deletion, any other key to cancel"

        await pilot.press("d")
        await pilot.pause()

        task = ctx.db.exec(select(AgendaItem).where(AgendaItem.name == "Pay rent")).one()
        assert task.status == "deleted"
        assert all("Pay rent" not in title for title in _sidebar_titles(app))
