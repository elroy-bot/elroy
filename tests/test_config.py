from pathlib import Path

from rich.table import Table

from elroy.tools.developer import print_config
from tests.utils import process_test_message


def test_print_config(ctx):
    ctx.config_path = Path(__file__).parent / "fixtures" / "test_config.yml"
    assert isinstance(print_config(ctx), Table)


def test_custom_config(ctx):
    ctx.config_path = Path(__file__).parent / "fixtures" / "test_config.yml"
    process_test_message(ctx, "hello world")
