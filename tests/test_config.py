from inspect import signature
from pathlib import Path

from rich.table import Table

from elroy.cli.main import CLI_ONLY_PARAMS, MODEL_ALIASES, common
from elroy.cli.options import DEPRECATED_KEYS
from elroy.config.llm import DEFAULTS_CONFIG
from elroy.tools.developer import print_config
from tests.utils import process_test_message


def test_cli_params_match_defaults():

    # Get all parameter names from the common function
    sig = signature(common)
    # Filter out ctx, config_file, and command flags.
    cli_params = {
        name
        for name in sig.parameters
        if name
        # This list are those that are either:
        # - application commands
        # - parameters that are relevant to one specific invocation
        not in [
            "config_path",
            "tool",
            "typer_ctx",
        ]
        + MODEL_ALIASES
    }

    # Get all keys from defaults.yml
    default_keys = set(DEFAULTS_CONFIG.keys())

    # Find any mismatches
    missing_from_defaults = cli_params - default_keys - DEPRECATED_KEYS - CLI_ONLY_PARAMS
    missing_from_cli = default_keys - cli_params - {"default_persona", "max_ingested_doc_lines"}

    # Build error message if there are mismatches
    error_msg = []
    if missing_from_defaults:
        error_msg.append(f"CLI params missing from defaults.yml: {missing_from_defaults}")
    if missing_from_cli:
        error_msg.append(f"Default keys missing from CLI params: {missing_from_cli}")

    assert not error_msg, "\n".join(error_msg)


def test_print_config(ctx):
    ctx.config_path = Path(__file__).parent / "fixtures" / "test_config.yml"
    assert isinstance(print_config(ctx), Table)


def test_custom_config(ctx):
    ctx.config_path = Path(__file__).parent / "fixtures" / "test_config.yml"
    process_test_message(ctx, "hello world")
