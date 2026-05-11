"""Small Textual widgets used by the Elroy TUI."""

from __future__ import annotations

from collections.abc import Iterable

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import ContentSwitcher, Label, ListItem, ListView, RichLog, Static, Tab, Tabs

from ..core.sidebar_models import SidebarEntry


class StatusBar(Label):
    """Reactive status bar label."""

    status_text: reactive[str] = reactive("")

    def watch_status_text(self, status_text: str) -> None:
        self.update(status_text)


class ConversationPane(Vertical):
    """Encapsulates conversation history and streaming output."""

    def compose(self) -> ComposeResult:
        yield RichLog(id="history-log", wrap=True, highlight=False, markup=False)
        yield Static("", id="streaming-output")

    def write_history(self, renderable) -> None:
        self.query_one("#history-log", RichLog).write(renderable)

    def set_streaming_text(self, text: str, style: str) -> None:
        self.query_one("#streaming-output", Static).update(Text(text, style=style))

    def clear_streaming(self) -> None:
        self.query_one("#streaming-output", Static).update("")

    def focus_history(self) -> None:
        self.query_one("#history-log", RichLog).focus()

    def history_has_focus(self) -> bool:
        return self.query_one("#history-log", RichLog).has_focus

    def set_history_active(self, active: bool) -> None:
        self.set_class(active, "active")


class SidebarListView(ListView):
    """Sidebar list view tagged with its owning section."""

    def __init__(self, section: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.section = section


class SidebarPanel(Vertical):
    """Encapsulates the sidebar tabs and list views."""

    SECTIONS = ("memories", "agenda", "improvements", "feature_requests", "codex_sessions")

    class SectionChanged(Message):
        def __init__(self, section: str) -> None:
            super().__init__()
            self.section = section

    class EntryHighlighted(Message):
        def __init__(self, section: str, index: int | None) -> None:
            super().__init__()
            self.section = section
            self.index = index

    class EntrySelected(Message):
        def __init__(self, section: str, index: int) -> None:
            super().__init__()
            self.section = section
            self.index = index

    def compose(self) -> ComposeResult:
        yield Tabs(
            Tab("Memories", id="memories-tab"),
            Tab("Agenda", id="agenda-tab"),
            Tab("Improvements", id="improvements-tab"),
            Tab("Feature Requests", id="feature_requests-tab"),
            Tab("Codex Sessions", id="codex_sessions-tab"),
            active="memories-tab",
            id="sidebar-tabs",
        )
        with ContentSwitcher(initial="memories-list", id="sidebar-switcher"):
            yield SidebarListView("memories", id="memories-list", classes="panel-list")
            yield SidebarListView("agenda", id="agenda-list", classes="panel-list")
            yield SidebarListView("improvements", id="improvements-list", classes="panel-list")
            yield SidebarListView("feature_requests", id="feature_requests-list", classes="panel-list")
            yield SidebarListView("codex_sessions", id="codex_sessions-list", classes="panel-list")

    @property
    def current_section(self) -> str:
        active = self.query_one("#sidebar-tabs", Tabs).active or "memories-tab"
        return self.section_for_tab_id(active) or "memories"

    def switch_section(self, section: str) -> None:
        self.query_one("#sidebar-tabs", Tabs).active = self._tab_id(section)
        self.query_one("#sidebar-switcher", ContentSwitcher).current = self._list_id(section)

    def list_view(self, section: str) -> SidebarListView:
        return self.query_one(f"#{self._list_id(section)}", SidebarListView)

    def current_list_view(self) -> SidebarListView:
        return self.list_view(self.current_section)

    def set_entries(self, entries_by_section: dict[str, list[SidebarEntry]]) -> None:
        for section in self.SECTIONS:
            list_view = self.list_view(section)
            list_view.clear()
            entries = entries_by_section[section]
            list_view.extend([ListItem(Label(entry.title), name=entry.ref.key) for entry in entries])

    def render_entries(self, entries_by_section: dict[str, list[SidebarEntry]], selected_indices: dict[str, int | None]) -> None:
        self.set_entries(entries_by_section)
        for section in self.SECTIONS:
            self.call_after_refresh(self.apply_selection, section, selected_indices.get(section))

    def apply_selection(self, section: str, index: int | None) -> None:
        list_view = self.list_view(section)
        if index is None:
            list_view.index = None
            return
        if list_view.index == index:
            list_view.index = None
        list_view.index = index

    def current_index(self, section: str) -> int | None:
        return self.list_view(section).index

    def focus_current_list(self) -> None:
        self.current_list_view().focus()

    def sidebar_lists(self) -> Iterable[SidebarListView]:
        return (self.list_view(section) for section in self.SECTIONS)

    def section_for_list(self, list_view: SidebarListView) -> str:
        return list_view.section

    def section_for_tab_id(self, tab_id: str) -> str | None:
        return {self._tab_id(section): section for section in self.SECTIONS}.get(tab_id)

    def set_browse_active(self, active_section: str | None) -> None:
        for section in self.SECTIONS:
            self.list_view(section).set_class(active_section == section, "active")

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        section = self.section_for_tab_id(event.tab.id or "")
        if section is None:
            return
        self.query_one("#sidebar-switcher", ContentSwitcher).current = self._list_id(section)
        self.post_message(self.SectionChanged(section))
        event.stop()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if not isinstance(event.list_view, SidebarListView):
            return
        self.post_message(self.EntryHighlighted(event.list_view.section, event.list_view.index))
        event.stop()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.list_view, SidebarListView) or event.index is None:
            return
        self.post_message(self.EntrySelected(event.list_view.section, event.index))
        event.stop()

    def _tab_id(self, section: str) -> str:
        return f"{section}-tab"

    def _list_id(self, section: str) -> str:
        return f"{section}-list"

    def _list_items(self, section: str) -> list[ListItem]:
        return [child for child in self.list_view(section).children if isinstance(child, ListItem)]
