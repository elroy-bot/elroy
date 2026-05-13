from textual.worker import WorkerState

from elroy.ui.state import WorkerStatus
from elroy.ui.status import StatusController, WorkerTransition


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
