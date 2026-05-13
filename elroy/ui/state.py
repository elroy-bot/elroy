"""Plain state models for the Textual app."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BrowseTarget = Literal["sidebar", "history"]
BrowseActionKind = Literal["move", "cycle", "switch_section", "open", "focus_chat"]
AppKeyActionKind = Literal["quit", "cancel_stream", "focus_memories", "focus_agenda", "toggle_browse"]
FocusTarget = Literal["chat", "sidebar", "history"]
SIDEBAR_SECTION_KEYS = {
    "m": "memories",
    "g": "agenda",
    "r": "improvements",
    "f": "feature_requests",
    "s": "codex_sessions",
}


@dataclass(frozen=True)
class BrowseAction:
    """Declarative result of a browse-mode keypress."""

    kind: BrowseActionKind
    delta: int = 0
    section: str | None = None


@dataclass(frozen=True)
class AppKeyAction:
    """Declarative result of an app-level keypress."""

    kind: AppKeyActionKind


@dataclass
class BrowseState:
    """Owns browse mode, target, and sidebar selection state."""

    sections: tuple[str, ...]
    is_browsing: bool = False
    target: BrowseTarget = "sidebar"
    panel_indices: dict[str, int | None] = field(init=False)

    def __post_init__(self) -> None:
        self.panel_indices = dict.fromkeys(self.sections)

    def focus_chat(self) -> None:
        self.is_browsing = False

    def focus_sidebar(self) -> None:
        self.is_browsing = True
        self.target = "sidebar"

    def focus_history(self) -> None:
        self.is_browsing = True
        self.target = "history"

    def focus_target(self) -> FocusTarget:
        if not self.is_browsing:
            return "chat"
        return self.target

    def toggle_mode(self) -> None:
        if self.is_browsing:
            self.focus_chat()
        else:
            self.focus_sidebar()

    def cycle_target(self) -> None:
        self.target = "history" if self.target == "sidebar" else "sidebar"
        self.is_browsing = True

    def browse_action_for_key(self, key: str, current_section: str, current_index: int | None) -> BrowseAction | None:
        if key in {"j", "down"}:
            return BrowseAction(kind="move", delta=1)
        if key in {"k", "up"}:
            return BrowseAction(kind="move", delta=-1)
        if key in {"left", "right"} and self.target == "sidebar":
            return BrowseAction(
                kind="switch_section",
                section=self._adjacent_section(current_section, delta=-1 if key == "left" else 1),
            )
        if key == "tab":
            return BrowseAction(kind="cycle")
        if key in SIDEBAR_SECTION_KEYS:
            return BrowseAction(kind="switch_section", section=SIDEBAR_SECTION_KEYS[key])
        if key == "enter" and self.target == "sidebar" and current_index is not None:
            return BrowseAction(kind="open", section=current_section)
        if key in {"escape", "i", "a"}:
            return BrowseAction(kind="focus_chat")
        return None

    def app_action_for_key(self, key: str) -> AppKeyAction | None:
        if key == "ctrl+d":
            return AppKeyAction(kind="quit")
        if key == "ctrl+c":
            return AppKeyAction(kind="cancel_stream")
        if key == "ctrl+m":
            return AppKeyAction(kind="focus_memories")
        if key == "ctrl+a":
            return AppKeyAction(kind="focus_agenda")
        if key == "escape" and self.is_browsing:
            return AppKeyAction(kind="toggle_browse")
        return None

    def recovery_focus_target(self, *, chat_has_focus: bool, history_has_focus: bool, sidebar_has_focus: bool) -> FocusTarget | None:
        if chat_has_focus or history_has_focus or sidebar_has_focus:
            return None
        return self.focus_target()

    def remember_selection(self, section: str, index: int | None) -> None:
        self.panel_indices[section] = index

    def clamp_index(self, section: str, entry_count: int) -> int | None:
        if entry_count <= 0:
            self.panel_indices[section] = None
            return None

        saved_index = self.panel_indices[section]
        if saved_index is None:
            saved_index = 0
        saved_index = max(0, min(saved_index, entry_count - 1))
        self.panel_indices[section] = saved_index
        return saved_index

    def move_selection(self, section: str, entry_count: int, delta: int, fallback_index: int | None = None) -> int | None:
        if entry_count <= 0:
            self.panel_indices[section] = None
            return None

        current_index = self.panel_indices[section]
        if current_index is None:
            current_index = fallback_index if fallback_index is not None else 0

        next_index = max(0, min(current_index + delta, entry_count - 1))
        self.panel_indices[section] = next_index
        return next_index

    def _adjacent_section(self, current_section: str, delta: int) -> str:
        try:
            index = self.sections.index(current_section)
        except ValueError:
            index = 0
        return self.sections[(index + delta) % len(self.sections)]


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
