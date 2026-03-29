import asyncio
from datetime import date

import pytest
from textual.widgets import Input, ListView, Tabs

from elroy.config.paths import get_agenda_dir
from elroy.core.ctx import ElroyContext
from elroy.io.formatters.rich_formatter import RichFormatter
from elroy.io.textual_app import BufferMode, ElroyApp, MemoryDetailModal
from elroy.repository.agenda.file_storage import write_agenda_item


@pytest.fixture
def elroy_home(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("ELROY_HOME", str(tmp_path))
    return tmp_path


def _make_app(ctx: ElroyContext, rich_formatter: RichFormatter) -> ElroyApp:
    return ElroyApp(
        ctx=ctx,
        formatter=rich_formatter,
        enable_greeting=False,
        show_internal_thought=False,
        show_memory_panel=True,
    )


async def _wait_for_list_items(pilot, expected_count: int = 1) -> None:
    list_view = pilot.app.query_one("#memory-list", ListView)
    for _ in range(20):
        if len(list_view.children) >= expected_count:
            return
        await pilot.pause(0.05)
    raise AssertionError(f"Expected at least {expected_count} list item(s), found {len(list_view.children)}")


def test_clicking_buffer_tabs_does_not_steal_input_focus(ctx: ElroyContext, rich_formatter: RichFormatter, elroy_home) -> None:
    async def run() -> None:
        app = _make_app(ctx, rich_formatter)
        async with app.run_test(headless=True, size=(120, 40)) as pilot:
            await pilot.pause(0.2)

            input_widget = app.query_one("#chat-input", Input)
            tabs = app.query_one("#buffer-tabs", Tabs)

            assert input_widget.has_focus

            await pilot.click("#tab-reminders")
            await pilot.pause(0.2)

            assert input_widget.has_focus
            assert not tabs.has_focus
            assert tabs.active == "tab-reminders"
            assert app._right_panel_mode == BufferMode.REMINDERS

    asyncio.run(run())


def test_browse_mode_tab_cycles_buffers(ctx: ElroyContext, rich_formatter: RichFormatter, elroy_home) -> None:
    async def run() -> None:
        app = _make_app(ctx, rich_formatter)
        async with app.run_test(headless=True, size=(120, 40)) as pilot:
            await pilot.pause(0.2)

            list_view = app.query_one("#memory-list", ListView)
            tabs = app.query_one("#buffer-tabs", Tabs)

            await pilot.press("escape")
            await pilot.pause(0.1)

            assert list_view.has_focus
            assert app._right_panel_mode == BufferMode.MEMORIES
            assert tabs.active == "tab-memories"

            await pilot.press("tab")
            await pilot.pause(0.2)

            assert list_view.has_focus
            assert app._right_panel_mode == BufferMode.REMINDERS
            assert tabs.active == "tab-reminders"

            await pilot.press("shift+tab")
            await pilot.pause(0.2)

            assert list_view.has_focus
            assert app._right_panel_mode == BufferMode.MEMORIES
            assert tabs.active == "tab-memories"

    asyncio.run(run())


def test_closing_detail_modal_restores_chat_input_focus(ctx: ElroyContext, rich_formatter: RichFormatter, elroy_home) -> None:
    write_agenda_item(get_agenda_dir(), "Write Q2 report", "Write the Q2 report.", date.today())

    async def run() -> None:
        app = _make_app(ctx, rich_formatter)
        async with app.run_test(headless=True, size=(120, 40)) as pilot:
            await pilot.pause(0.2)

            input_widget = app.query_one("#chat-input", Input)
            list_view = app.query_one("#memory-list", ListView)

            await pilot.click("#tab-agenda")
            await _wait_for_list_items(pilot)

            await pilot.press("escape")
            await pilot.pause(0.1)
            list_view.index = 0

            await pilot.press("enter")
            await pilot.pause(0.2)

            assert len(app.screen_stack) == 2
            assert isinstance(app.screen_stack[-1], MemoryDetailModal)

            await pilot.press("escape")
            await pilot.pause(0.2)

            assert len(app.screen_stack) == 1
            assert input_widget.has_focus

    asyncio.run(run())
