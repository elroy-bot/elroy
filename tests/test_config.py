from inspect import signature
from pathlib import Path

import yaml
from typer.testing import CliRunner

from elroy.cli.main import app, common


def test_config_precedence():
    """Test that config values are properly prioritized:
    CLI args > env vars > config file > defaults
    """
    runner = CliRunner()
    config_path = Path(__file__).parent / "fixtures" / "test_config.yml"

    # Test 1: CLI args override everything
    result = runner.invoke(
        app,
        ["--config", str(config_path), "--chat-model", "cli_model", "--show-config"],
        env={"ELROY_CHAT_MODEL": "env_model"},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "cli_model" in result.stdout
    assert "env_model" not in result.stdout
    assert "config_file_model" not in result.stdout

    # Test 2: Environment variables override config file
    result = runner.invoke(
        app,
        ["--config", str(config_path), "--show-config"],
        env={"ELROY_CHAT_MODEL": "env_model"},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "env_model" in result.stdout
    assert "config_file_model" not in result.stdout

    # Test 3: Config file overrides defaults
    result = runner.invoke(
        app,
        ["--config", str(config_path), "--show-config"],
        env={},  # No environment variables
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "config_file_model" in result.stdout


def test_cli_params_match_defaults():
    # Load defaults.yml
    with open("elroy/config/defaults.yml") as f:
        defaults = yaml.safe_load(f)

    # Get all parameter names from the common function
    sig = signature(common)
    # Filter out ctx, config_file, and command flags.
    cli_params = {
        name
        for name in sig.parameters
        if name
        not in [
            "ctx",
            "version",
            "config_file",
            "show_config",
            "chat",
            "remember",
            "remember_file",
            "list_models",
        ]
    }

    # Get all keys from defaults.yml
    default_keys = set(defaults.keys())

    # Find any mismatches
    missing_from_defaults = cli_params - default_keys
    missing_from_cli = default_keys - cli_params

    # Build error message if there are mismatches
    error_msg = []
    if missing_from_defaults:
        error_msg.append(f"CLI params missing from defaults.yml: {missing_from_defaults}")
    if missing_from_cli:
        error_msg.append(f"Default keys missing from CLI params: {missing_from_cli}")

    assert not error_msg, "\n".join(error_msg)
