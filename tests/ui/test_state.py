from textual.worker import WorkerState

from elroy.ui.state import AppKeyAction, BrowseAction, BrowseState, WorkerStatus
from elroy.ui.status import StatusController, WorkerTransition


def test_browse_state_clamps_and_cycles_targets() -> None:
    state = BrowseState(("memories", "agenda"))

    assert state.is_browsing is False
    assert state.target == "sidebar"

    state.toggle_mode()
    assert state.is_browsing is True
    assert state.target == "sidebar"

    state.cycle_target()
    assert state.target == "history"

    state.remember_selection("agenda", 9)
    assert state.clamp_index("agenda", 3) == 2
    assert state.panel_indices["agenda"] == 2

    assert state.move_selection("agenda", 3, -1) == 1
    assert state.move_selection("agenda", 0, 1) is None
    assert state.panel_indices["agenda"] is None


def test_browse_state_maps_keys_to_actions() -> None:
    state = BrowseState(("memories", "agenda"))
    state.focus_sidebar()

    assert state.browse_action_for_key("j", "memories", 0) == BrowseAction(kind="move", delta=1)
    assert state.browse_action_for_key("k", "memories", 0) == BrowseAction(kind="move", delta=-1)
    assert state.browse_action_for_key("tab", "memories", 0) == BrowseAction(kind="cycle")
    assert state.browse_action_for_key("m", "agenda", 1) == BrowseAction(kind="switch_section", section="memories")
    assert state.browse_action_for_key("g", "memories", 1) == BrowseAction(kind="switch_section", section="agenda")
    assert state.browse_action_for_key("enter", "agenda", 2) == BrowseAction(kind="open", section="agenda")
    assert state.browse_action_for_key("i", "agenda", 2) == BrowseAction(kind="focus_chat")
    assert state.browse_action_for_key("x", "agenda", 2) is None

    state.focus_history()
    assert state.browse_action_for_key("enter", "agenda", 2) is None


def test_browse_state_maps_global_app_keys_to_actions() -> None:
    state = BrowseState(("memories", "agenda"))

    assert state.app_action_for_key("ctrl+d") == AppKeyAction(kind="quit")
    assert state.app_action_for_key("ctrl+c") == AppKeyAction(kind="cancel_stream")
    assert state.app_action_for_key("ctrl+m") == AppKeyAction(kind="focus_memories")
    assert state.app_action_for_key("ctrl+a") == AppKeyAction(kind="focus_agenda")
    assert state.app_action_for_key("escape") is None

    state.focus_sidebar()
    assert state.app_action_for_key("escape") == AppKeyAction(kind="toggle_browse")


def test_browse_state_computes_focus_targets() -> None:
    state = BrowseState(("memories", "agenda"))

    assert state.focus_target() == "chat"
    assert state.recovery_focus_target(chat_has_focus=False, history_has_focus=False, sidebar_has_focus=False) == "chat"
    assert state.recovery_focus_target(chat_has_focus=True, history_has_focus=False, sidebar_has_focus=False) is None

    state.focus_sidebar()
    assert state.focus_target() == "sidebar"
    assert state.recovery_focus_target(chat_has_focus=False, history_has_focus=False, sidebar_has_focus=False) == "sidebar"

    state.focus_history()
    assert state.focus_target() == "history"
    assert state.recovery_focus_target(chat_has_focus=False, history_has_focus=False, sidebar_has_focus=False) == "history"


def test_worker_status_blocks_submit_and_builds_status_text() -> None:
    status = WorkerStatus("abc")

    assert status.is_submit_blocked() is False
    assert status.status_text("gpt-test", None) == "● gpt-test"

    status.start_group("chat-stream")
    status.set_status_message("thinking...")
    assert status.is_submit_blocked() is True
    assert status.status_text("gpt-test", "idle") == "a thinking..."

    status.advance_spinner()
    assert status.status_text("gpt-test", "idle") == "b thinking..."

    status.finish_group("chat-stream")
    status.start_group("sidebar-refresh")
    assert status.status_text("gpt-test", "idle") == "● gpt-test  ⟳ sidebar-refresh"

    status.finish_group("sidebar-refresh")
    assert status.status_text("gpt-test", "idle") == "● gpt-test  ⟳ idle"


def test_status_controller_tracks_worker_transitions() -> None:
    controller = StatusController("abc")

    assert controller.should_track_group("chat-stream") is True
    assert controller.should_track_group("unknown") is False
    assert controller.is_submit_blocked() is False

    running = controller.handle_worker_state_changed("command-action", WorkerState.RUNNING, None)
    assert running == WorkerTransition(should_render=True, status_message="running command")
    controller.set_status_message(running.status_message or "")
    assert controller.active_groups == {"command-action"}
    assert controller.is_submit_blocked() is True

    error = controller.handle_worker_state_changed("command-action", WorkerState.ERROR, "boom")
    assert error == WorkerTransition(should_render=True, error_message="boom")
    assert controller.active_groups == set()

    cancelled = controller.handle_worker_state_changed("chat-stream", WorkerState.CANCELLED, None)
    assert cancelled == WorkerTransition(should_render=True, notify_cancelled=True)

    controller.handle_worker_state_changed("chat-stream", WorkerState.RUNNING, None)
    assert controller.should_render_background_status() is False
    controller.reset_spinner()
    controller.advance_spinner()
    assert controller.status.status_text("gpt-test", "idle").startswith("b ")
