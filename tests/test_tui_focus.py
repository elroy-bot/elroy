"""
Textual pilot tests for TUI focus management.

These tests guard against the recurring class of bug where focus escapes to an
unexpected widget, leaving the user unable to type or navigate.  Run with:

    just test tests/test_tui_focus.py

Each test drives the app with pilot.press() and asserts which widget is focused
afterward — the only reliable way to catch silent focus regressions.
"""

import pytest
from textual.widgets import Input, ListView

from elroy.io.textual_app import ElroyApp

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _focused_id(app: ElroyApp) -> str | None:
    return getattr(app.focused, "id", None)


def _focus_chain_ids(app: ElroyApp) -> list[str | None]:
    return [getattr(w, "id", None) for w in app.screen.focus_chain]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def elroy_app(ctx, rich_formatter):
    """Lightweight ElroyApp suitable for focus testing (no greeting, no panel)."""
    return ElroyApp(
        ctx=ctx,
        formatter=rich_formatter,
        enable_greeting=False,
        show_internal_thought=False,
        show_memory_panel=True,
    )


# ---------------------------------------------------------------------------
# Focus-chain integrity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_only_chat_input_in_focus_chain_on_startup(elroy_app):
    """RichLog, Tabs, and ListView must all be excluded from the focus chain.

    If any of these appear, Tab-cycling will land on them and the user loses
    control of the app.
    """
    async with elroy_app.run_test(headless=True, size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        chain_ids = _focus_chain_ids(elroy_app)
        assert chain_ids == ["chat-input"], (
            f"Unexpected widgets in focus chain: {chain_ids}. Any focusable widget beyond #chat-input lets Tab escape to it."
        )


# ---------------------------------------------------------------------------
# Input mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tab_in_input_mode_keeps_focus_on_input(elroy_app):
    """Tab must not cycle focus away from the chat input."""
    async with elroy_app.run_test(headless=True, size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        inp = elroy_app.query_one("#chat-input", Input)
        assert elroy_app.focused is inp

        await pilot.press("tab")
        await pilot.pause(0.2)
        assert elroy_app.focused is inp, f"After Tab, focused={_focused_id(elroy_app)!r} — focus escaped input"


@pytest.mark.asyncio
async def test_typing_works_after_tab_in_input_mode(elroy_app):
    """Characters typed after Tab must appear in the input widget."""
    async with elroy_app.run_test(headless=True, size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        inp = elroy_app.query_one("#chat-input", Input)

        await pilot.press("tab")
        await pilot.pause(0.2)
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.pause(0.1)

        assert inp.value == "hello", f"Expected 'hello', got {inp.value!r}"


# ---------------------------------------------------------------------------
# Browse mode entry / exit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escape_enters_browse_mode(elroy_app):
    """Escape must move focus from the input to the memory list."""
    async with elroy_app.run_test(headless=True, size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        lv = elroy_app.query_one("#memory-list", ListView)

        await pilot.press("escape")
        await pilot.pause(0.3)

        assert lv.has_focus, f"After Escape, expected list-view focus, got {_focused_id(elroy_app)!r}"


@pytest.mark.asyncio
async def test_escape_twice_returns_to_input(elroy_app):
    """Two Escape presses must end up back on the chat input."""
    async with elroy_app.run_test(headless=True, size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        inp = elroy_app.query_one("#chat-input", Input)

        await pilot.press("escape")
        await pilot.pause(0.3)
        await pilot.press("escape")
        await pilot.pause(0.2)

        assert elroy_app.focused is inp, f"After Escape×2, expected input focus, got {_focused_id(elroy_app)!r}"


@pytest.mark.asyncio
async def test_typing_works_after_escape_twice(elroy_app):
    """User must be able to type after returning from browse mode via Escape."""
    async with elroy_app.run_test(headless=True, size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        inp = elroy_app.query_one("#chat-input", Input)

        await pilot.press("escape")
        await pilot.pause(0.3)
        await pilot.press("escape")
        await pilot.pause(0.2)
        await pilot.press("h", "i")
        await pilot.pause(0.1)

        assert inp.value == "hi", f"Expected 'hi', got {inp.value!r}"


# ---------------------------------------------------------------------------
# Browse mode navigation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tab_in_browse_mode_keeps_focus_on_list(elroy_app):
    """Tab in browse mode must cycle buffers, not move focus elsewhere."""
    async with elroy_app.run_test(headless=True, size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        lv = elroy_app.query_one("#memory-list", ListView)

        await pilot.press("escape")
        await pilot.pause(0.3)
        assert lv.has_focus

        await pilot.press("tab")
        await pilot.pause(0.3)
        assert lv.has_focus, f"After browse-Tab, expected list focus, got {_focused_id(elroy_app)!r}"


@pytest.mark.asyncio
async def test_i_in_browse_mode_returns_to_input(elroy_app):
    """Pressing 'i' in browse mode must return focus to the chat input."""
    async with elroy_app.run_test(headless=True, size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        inp = elroy_app.query_one("#chat-input", Input)

        await pilot.press("escape")
        await pilot.pause(0.3)
        await pilot.press("i")
        await pilot.pause(0.2)

        assert elroy_app.focused is inp, f"After browse→i, expected input focus, got {_focused_id(elroy_app)!r}"


@pytest.mark.asyncio
async def test_typing_works_after_browse_and_return(elroy_app):
    """Full round-trip: enter browse mode, return with 'i', type, verify."""
    async with elroy_app.run_test(headless=True, size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        inp = elroy_app.query_one("#chat-input", Input)

        await pilot.press("escape")
        await pilot.pause(0.3)
        await pilot.press("tab")  # cycle buffer
        await pilot.pause(0.3)
        await pilot.press("i")  # return to input
        await pilot.pause(0.2)
        await pilot.press("t", "e", "s", "t")
        await pilot.pause(0.1)

        assert inp.value == "test", f"Expected 'test', got {inp.value!r}"
