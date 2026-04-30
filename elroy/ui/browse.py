"""Browse/focus controller for the Textual app."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .state import AppKeyAction, BrowseAction, BrowseState, FocusTarget


class BrowseController:
    """Coordinates browse state with sidebar/history/chat widgets."""

    def __init__(self, browse_state: BrowseState):
        self.state = browse_state

    @property
    def is_browsing(self) -> bool:
        return self.state.is_browsing

    @property
    def target(self) -> str:
        return self.state.target

    @property
    def panel_indices(self) -> dict[str, int | None]:
        return self.state.panel_indices

    def app_action_for_key(self, key: str) -> AppKeyAction | None:
        return self.state.app_action_for_key(key)

    def browse_action_for_key(self, key: str, current_section: str, current_index: int | None) -> BrowseAction | None:
        return self.state.browse_action_for_key(key, current_section, current_index)

    def recovery_focus_target(self, *, chat_has_focus: bool, history_has_focus: bool, sidebar_has_focus: bool) -> FocusTarget | None:
        return self.state.recovery_focus_target(
            chat_has_focus=chat_has_focus,
            history_has_focus=history_has_focus,
            sidebar_has_focus=sidebar_has_focus,
        )

    def remember_selection(self, section: str, index: int | None) -> None:
        self.state.remember_selection(section, index)

    def focus_chat(self, chat_input) -> None:
        self.state.focus_chat()
        chat_input.focus()

    def focus_sidebar(self) -> None:
        self.state.focus_sidebar()

    def focus_history(self, conversation_pane) -> None:
        self.state.focus_history()
        conversation_pane.focus_history()

    def resolved_sidebar_index(self, section: str, entries: Sequence[object]) -> int | None:
        if not entries:
            self.state.remember_selection(section, None)
            return None
        return self.state.clamp_index(section, len(entries))

    def apply_sidebar_selection(self, sidebar_panel, section: str, entries: Sequence[object]) -> None:
        sidebar_panel.apply_selection(section, self.resolved_sidebar_index(section, entries))

    def move_sidebar_selection(self, sidebar_panel, section: str, entries: Sequence[object], delta: int) -> None:
        if not entries:
            self.state.remember_selection(section, None)
            sidebar_panel.apply_selection(section, None)
            return

        next_index = self.state.move_selection(section, len(entries), delta, sidebar_panel.current_index(section))
        assert next_index is not None
        sidebar_panel.apply_selection(section, next_index)

    def switch_sidebar_section(
        self,
        sidebar_panel,
        section: str,
        entries_by_section: Mapping[str, Sequence[object]],
        focus_sidebar: bool = False,
    ) -> None:
        if section not in entries_by_section:
            return
        sidebar_panel.switch_section(section)
        self.apply_sidebar_selection(sidebar_panel, section, entries_by_section[section])
        if focus_sidebar or self.state.is_browsing:
            self.state.focus_sidebar()
            sidebar_panel.focus_current_list()
            sidebar_panel.call_after_refresh(self.apply_sidebar_selection, sidebar_panel, section, entries_by_section[section])

    def focus_target(
        self,
        target: str,
        chat_input,
        conversation_pane,
        sidebar_panel,
        current_section: str,
        entries: Sequence[object],
    ) -> None:
        assert target in {"chat", "sidebar", "history"}
        if target == "chat":
            self.focus_chat(chat_input)
            return
        if target == "history":
            self.focus_history(conversation_pane)
            return
        self.state.focus_sidebar()
        sidebar_panel.focus_current_list()
        self.apply_sidebar_selection(sidebar_panel, current_section, entries)

    def focus_current_target(self, chat_input, conversation_pane, sidebar_panel, current_section: str, entries: Sequence[object]) -> None:
        self.focus_target(self.state.focus_target(), chat_input, conversation_pane, sidebar_panel, current_section, entries)

    def cycle_target(self, chat_input, conversation_pane, sidebar_panel, current_section: str, entries: Sequence[object]) -> None:
        self.state.cycle_target()
        self.focus_current_target(chat_input, conversation_pane, sidebar_panel, current_section, entries)

    def render_browse_state(self, conversation_pane, sidebar_panel, current_section: str) -> None:
        history_active = self.state.is_browsing and self.state.target == "history"
        conversation_pane.set_history_active(history_active)
        active_sidebar_section = current_section if self.state.is_browsing and self.state.target == "sidebar" else None
        sidebar_panel.set_browse_active(active_sidebar_section)
