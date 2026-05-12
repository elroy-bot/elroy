from pathlib import Path

from rich.table import Table

from elroy.core.ctx import ElroyConfig
from elroy.tools.developer import print_config
from tests.utils import process_test_message


def test_print_config(ctx):
    ctx.config_path = Path(__file__).parent / "fixtures" / "test_config.yml"
    assert isinstance(print_config(ctx), Table)


def test_custom_config(ctx):
    ctx.config_path = Path(__file__).parent / "fixtures" / "test_config.yml"
    process_test_message(ctx, "hello world")


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
