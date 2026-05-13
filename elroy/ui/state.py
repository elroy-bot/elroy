"""Plain state models for the Textual app."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorkerStatus:
    """Owns worker activity and status message derivation."""

    spinner_chars: str
    active_groups: set[str] = field(default_factory=set)
    status_message: str = ""
    spinner_index: int = 0

    def is_submit_blocked(self) -> bool:
        return bool({"chat-stream", "command-action"} & self.active_groups)

    def reset_spinner(self) -> None:
        self.spinner_index = 0

    def advance_spinner(self) -> None:
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)

    def set_status_message(self, message: str) -> None:
        self.status_message = message

    def start_group(self, group: str) -> None:
        self.active_groups.add(group)

    def finish_group(self, group: str) -> None:
        self.active_groups.discard(group)

    def status_text(self, model_name: str, background_status: str | None) -> str:
        if "chat-stream" in self.active_groups:
            return f"{self.spinner_chars[self.spinner_index]} {self.status_message or 'thinking...'}"
        if self.active_groups:
            active = ", ".join(sorted(self.active_groups))
            return f"● {model_name}  ⟳ {active}"
        return f"● {model_name}  ⟳ {background_status}" if background_status else f"● {model_name}"
