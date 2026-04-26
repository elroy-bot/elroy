"""Status/worker controller for the Textual app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from textual.worker import WorkerState

from .state import WorkerStatus


@dataclass(frozen=True)
class WorkerTransition:
    """Declarative result of a worker state transition."""

    should_render: bool = False
    status_message: str | None = None
    error_message: str | None = None
    notify_cancelled: bool = False


class StatusController:
    """Coordinates worker groups, spinner state, and status text."""

    TRACKED_GROUPS: ClassVar[set[str]] = {
        "session-bootstrap",
        "chat-stream",
        "sidebar-refresh",
        "command-action",
        "deferred-context-refresh",
    }

    def __init__(self, spinner_chars: str):
        self.status = WorkerStatus(spinner_chars)

    @property
    def active_groups(self) -> set[str]:
        return self.status.active_groups

    def is_submit_blocked(self) -> bool:
        return self.status.is_submit_blocked()

    def set_status_message(self, message: str) -> None:
        self.status.set_status_message(message)

    def reset_spinner(self) -> None:
        self.status.reset_spinner()

    def advance_spinner(self) -> None:
        self.status.advance_spinner()

    def should_render_background_status(self) -> bool:
        return "chat-stream" not in self.status.active_groups

    def status_text(self, model_name: str, background_status: str | None) -> str:
        return self.status.status_text(model_name, background_status)

    def should_track_group(self, group: str) -> bool:
        return group in self.TRACKED_GROUPS

    def handle_worker_state_changed(self, group: str, state: WorkerState, error_message: str | None) -> WorkerTransition:
        if state == WorkerState.RUNNING:
            self.status.start_group(group)
            if group == "sidebar-refresh":
                return WorkerTransition(should_render=True, status_message="refreshing sidebar")
            if group == "command-action":
                return WorkerTransition(should_render=True, status_message="running command")
            return WorkerTransition(should_render=True)

        self.status.finish_group(group)
        if state == WorkerState.ERROR and error_message:
            return WorkerTransition(should_render=True, error_message=error_message)
        if state == WorkerState.CANCELLED and group == "chat-stream":
            return WorkerTransition(should_render=True, notify_cancelled=True)
        return WorkerTransition(should_render=True)
