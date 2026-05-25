from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

ELROY_PLUGIN_ATTR = "ELROY_PLUGIN"


@dataclass
class ElroyPlugin:
    """A plugin that can contribute tools and/or a sidebar UI panel to Elroy.

    To register a plugin, set an ``ELROY_PLUGIN`` module-level variable in a
    ``.py`` file inside the directory pointed to by ``contrib_tools_path``::

        # my_plugin.py
        from elroy.plugins.plugin import ElroyPlugin

        def _make_widget():
            from textual.widgets import Label
            from textual.widget import Widget

            class MyPanel(Widget):
                def compose(self):
                    yield Label("Hello from my plugin!")

            return MyPanel()

        ELROY_PLUGIN = ElroyPlugin(
            name="my_plugin",
            tab_label="My Plugin",
            widget_factory=_make_widget,
        )

    Textual imports should be kept inside ``widget_factory`` so that the plugin
    file can be loaded in non-UI contexts (e.g., background workers) without
    pulling in Textual.
    """

    name: str
    tab_label: str | None = None
    widget_factory: Callable[[], Any] | None = None
