from pathlib import Path

from elroy.plugins.plugin import ELROY_PLUGIN_ATTR
from elroy.plugins.registry import PluginRegistry


def _write_plugin_file(path: Path, name: str, tab_label: str) -> None:
    path.write_text(
        f"""\
from elroy.plugins.plugin import ElroyPlugin

def _make():
    from textual.widget import Widget
    return Widget()

{ELROY_PLUGIN_ATTR} = ElroyPlugin(name={name!r}, tab_label={tab_label!r}, widget_factory=_make)
""",
        encoding="utf-8",
    )


def _write_tool_only_file(path: Path) -> None:
    path.write_text(
        """\
from elroy.core.constants import tool

@tool
def my_contrib_tool(msg: str) -> str:
    \"\"\"A contrib tool.

    Args:
        msg: A message.
    \"\"\"
    return msg
""",
        encoding="utf-8",
    )


def test_registry_discovers_plugin_from_directory(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "my_contrib"
    plugin_dir.mkdir()
    _write_plugin_file(plugin_dir / "my_plugin.py", "my_plugin", "My Plugin")
    _write_tool_only_file(plugin_dir / "tools.py")

    registry = PluginRegistry.from_path(str(plugin_dir))
    assert len(registry.plugins) == 1
    plugin = registry.plugins[0]
    assert plugin.name == "my_plugin"
    assert plugin.tab_label == "My Plugin"
    assert callable(plugin.widget_factory)


def test_registry_skips_files_without_elroy_plugin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "contrib"
    plugin_dir.mkdir()
    _write_tool_only_file(plugin_dir / "tools.py")

    registry = PluginRegistry.from_path(str(plugin_dir))
    assert registry.plugins == []


def test_registry_skips_private_files(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "contrib"
    plugin_dir.mkdir()
    _write_plugin_file(plugin_dir / "_private.py", "private", "Private")

    registry = PluginRegistry.from_path(str(plugin_dir))
    assert registry.plugins == []


def test_registry_deduplicates_same_name(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "contrib"
    plugin_dir.mkdir()
    _write_plugin_file(plugin_dir / "a.py", "same_name", "Tab A")
    _write_plugin_file(plugin_dir / "b.py", "same_name", "Tab B")

    registry = PluginRegistry.from_path(str(plugin_dir))
    assert len(registry.plugins) == 1


def test_registry_from_none_path_returns_empty() -> None:
    registry = PluginRegistry.from_path(None)
    assert registry.plugins == []


def test_registry_warns_on_nonexistent_path(tmp_path: Path) -> None:
    registry = PluginRegistry.from_path(str(tmp_path / "does_not_exist"))
    assert registry.plugins == []


def test_plugin_without_tab_label_not_counted_as_ui_plugin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "contrib"
    plugin_dir.mkdir()
    (plugin_dir / "no_ui.py").write_text(
        f"""\
from elroy.plugins.plugin import ElroyPlugin
{ELROY_PLUGIN_ATTR} = ElroyPlugin(name="headless")
""",
        encoding="utf-8",
    )

    registry = PluginRegistry.from_path(str(plugin_dir))
    assert len(registry.plugins) == 1
    assert registry.plugins[0].tab_label is None
    assert registry.plugins[0].widget_factory is None


def test_invalid_elroy_plugin_attr_is_skipped(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "contrib"
    plugin_dir.mkdir()
    (plugin_dir / "bad.py").write_text(
        f"""\
{ELROY_PLUGIN_ATTR} = "this is not an ElroyPlugin"
""",
        encoding="utf-8",
    )

    registry = PluginRegistry.from_path(str(plugin_dir))
    assert registry.plugins == []
