"""Small Textual widgets used by the Elroy TUI."""

from __future__ import annotations

from collections.abc import Iterable

from rich.measure import measure_renderables
from rich.segment import Segment
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.geometry import Size
from textual.message import Message
from textual.reactive import reactive
from textual.strip import Strip
from textual.widgets import ContentSwitcher, Label, ListItem, ListView, RichLog, Tab, Tabs

from ..core.sidebar_models import SidebarEntry


class StatusBar(Label):
    """Reactive status bar label."""

    status_text: reactive[str] = reactive("")

    def watch_status_text(self, status_text: str) -> None:
        self.update(status_text)


class ConversationPane(Vertical):
    """Encapsulates conversation history."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._stream_start_line: int | None = None
        self._stream_line_count = 0

    def compose(self) -> ComposeResult:
        yield RichLog(id="history-log", wrap=True, highlight=False, markup=False)

    def write_history(self, renderable) -> None:
        self.query_one("#history-log", RichLog).write(renderable)

    def replace_history(self, renderables: list[object]) -> None:
        history_log = self.query_one("#history-log", RichLog)
        history_log.clear()
        for renderable in renderables:
            history_log.write(renderable)
        self._stream_start_line = None
        self._stream_line_count = 0

    def update_streaming(self, renderable) -> None:
        history_log = self.query_one("#history-log", RichLog)
        strips = self._render_to_strips(history_log, renderable)
        if not strips:
            strips = [Strip.blank(history_log.min_width)]

        start_line = len(history_log.lines) if self._stream_start_line is None else self._stream_start_line
        end_line = start_line + self._stream_line_count

        if self._stream_start_line is None:
            history_log.lines.extend(strips)
        else:
            history_log.lines[start_line:end_line] = strips

        self._stream_start_line = start_line
        self._stream_line_count = len(strips)
        self._refresh_history_log(history_log)

    def finalize_streaming(self) -> None:
        self._stream_start_line = None
        self._stream_line_count = 0

    def focus_history(self) -> None:
        self.query_one("#history-log", RichLog).focus()

    def history_has_focus(self) -> bool:
        return self.query_one("#history-log", RichLog).has_focus

    def set_history_active(self, active: bool) -> None:
        self.set_class(active, "active")

    def _render_to_strips(self, history_log: RichLog, renderable) -> list[Strip]:
        if not history_log._size_known:
            return []

        console = history_log.app.console
        render_options = console.options
        renderable = history_log._make_renderable(renderable)
        if history_log.wrap is False:
            render_options = render_options.update(overflow="ignore", no_wrap=True)

        renderable_width = measure_renderables(console, render_options, [renderable]).maximum
        scrollable_width = history_log.scrollable_content_region.width
        render_width = max(history_log.min_width, min(renderable_width, scrollable_width))
        render_options = render_options.update_width(render_width)

        segments = console.render(renderable, render_options)
        lines = list(Segment.split_lines(segments))
        strips = Strip.from_lines(lines)
        for strip in strips:
            strip.adjust_cell_length(render_width)
        return strips

    def _refresh_history_log(self, history_log: RichLog) -> None:
        history_log._line_cache.clear()
        history_log._widest_line_width = max((strip.cell_length for strip in history_log.lines), default=0)
        history_log.virtual_size = Size(history_log._widest_line_width, len(history_log.lines))
        history_log.refresh()
        history_log.scroll_end(animate=False, immediate=True, x_axis=False)


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
