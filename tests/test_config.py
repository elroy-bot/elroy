from pathlib import Path

from rich.table import Table

from elroy.cli.options import load_config_if_exists
from elroy.core.ctx import ElroyConfig
from elroy.core.session import init_elroy_session
from elroy.plugins.registry import PluginRegistry
from elroy.tools.developer import print_config
from tests.utils import process_test_message


def test_print_config(ctx):
    ctx.config_path = Path(__file__).parent / "fixtures" / "test_config.yml"
    assert isinstance(print_config(ctx), Table)


def test_custom_config(ctx):
    ctx.config_path = Path(__file__).parent / "fixtures" / "test_config.yml"
    process_test_message(ctx, "hello world")


def test_init_session_allows_source_checkout_on_main_branch(ctx, monkeypatch, tmp_path):
    monkeypatch.setattr("elroy.utils.git.source_tree_root", lambda: tmp_path)
    monkeypatch.setattr("elroy.utils.git.editable_install_root", lambda: None)
    monkeypatch.setattr("elroy.utils.git.get_current_branch", lambda _repo_root: "main")

    with init_elroy_session(ctx, None, check_db_migration=False, should_onboard_interactive=False):
        pass


def test_default_config_path_is_loaded(monkeypatch, tmp_path):
    home_dir = tmp_path / "elroy-home"
    config_path = home_dir / "elroy.conf.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("chat_model: gpt-5.4\n", encoding="utf-8")

    monkeypatch.setenv("ELROY_HOME", str(home_dir))
    monkeypatch.delenv("ELROY_CONFIG_PATH", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    ctx = ElroyConfig.init()

    assert ctx.model_config.chat_model == "gpt-5.4"


def test_default_contrib_path_is_created(monkeypatch, tmp_path):
    home_dir = tmp_path / "elroy-home"
    monkeypatch.setenv("ELROY_HOME", str(home_dir))
    monkeypatch.delenv("ELROY_CONFIG_PATH", raising=False)
    monkeypatch.delenv("ELROY_CONTRIB_TOOLS_PATH", raising=False)
    load_config_if_exists.cache_clear()

    ctx = ElroyConfig.init(chat_model="gpt-5.4")

    assert ctx.tool_config.contrib_tools_path == str(home_dir / "contrib")
    assert (home_dir / "contrib").is_dir()


def test_contrib_path_loads_tools_and_plugins(tmp_path):
    contrib_dir = tmp_path / "contrib"
    contrib_dir.mkdir()
    (contrib_dir / "tools.py").write_text(
        """\
from elroy.core.constants import tool

@tool
def contrib_answer() -> str:
    \"\"\"Return the contrib answer.

    Returns:
        The answer.
    \"\"\"
    return "from contrib"
""",
        encoding="utf-8",
    )
    (contrib_dir / "plugin.py").write_text(
        """\
from elroy.plugins.plugin import ElroyPlugin

def _make():
    from textual.widget import Widget
    return Widget()

ELROY_PLUGIN = ElroyPlugin(name="contrib_panel", tab_label="Contrib", widget_factory=_make)
""",
        encoding="utf-8",
    )

    ctx = ElroyConfig.init(chat_model="gpt-5.4", include_base_tools=False, contrib_tools_path=str(contrib_dir))

    assert "contrib_answer" in ctx.tool_registry
    registry = PluginRegistry.from_path(ctx.tool_config.contrib_tools_path)
    assert [plugin.name for plugin in registry.plugins] == ["contrib_panel"]
