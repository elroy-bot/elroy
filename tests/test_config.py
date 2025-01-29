from inspect import signature
from pathlib import Path

import pytest
from rich.table import Table
from tests.utils import process_test_message
from typer.testing import CliRunner

from elroy.cli.main import MODEL_ALIASES, app, common
from elroy.cli.options import DEPRECATED_KEYS
from elroy.config.llm import DEFAULTS_CONFIG
from elroy.tools.developer import print_config


@pytest.mark.skip("CliRunner not working well in multi threaded app")
def test_config_precedence(capsys: pytest.CaptureFixture):
    """Test that config values are properly prioritized:
    CLI args > env vars > config file > defaults
    """
    with capsys.disabled():
        runner = CliRunner()
        config_path = Path(__file__).parent / "fixtures" / "test_config.yml"

        # Test 1: CLI args override everything
        result = runner.invoke(
            app,
            args=["--config", str(config_path), "--chat-model", "gpt-4o-mini", "print-config"],
            env={"ELROY_CHAT_MODEL": "env_model"},
            catch_exceptions=True,
        )
        assert result.exit_code == 0
        assert "gpt-4o-mini" in result.stdout
        assert "env_model" not in result.stdout
        assert "config_file_model" not in result.stdout

        # Test 2: Environment variables override config file
        result = runner.invoke(
            app,
            ["--config", str(config_path), "print-config"],
            env={"ELROY_CHAT_MODEL": "gpt-4o-mini"},
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "gpt-4o-mini" in result.stdout
        assert "config_file_model" not in result.stdout

        # Test 3: Config file overrides defaults
        result = runner.invoke(
            app,
            ["--config", str(config_path), "print-config"],
            env={},  # No environment variables
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "gpt-4o-mini" in result.stdout


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
    missing_from_defaults = cli_params - default_keys
    missing_from_cli = default_keys - cli_params - {"default_persona"} - DEPRECATED_KEYS

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
