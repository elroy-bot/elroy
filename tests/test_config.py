from inspect import signature
from pathlib import Path

import yaml
from typer.testing import CliRunner

from elroy.cli.main import app, common
from elroy.llm.persona import get_persona
from elroy.tools.user_preferences import reset_system_persona, set_system_persona


def test_config_precedence():
    """Test that config values are properly prioritized:
    CLI args > env vars > config file > defaults
    """
    runner = CliRunner()
    config_path = Path(__file__).parent / "fixtures" / "test_config.yml"

    # Test 1: CLI args override everything
    result = runner.invoke(
        app,
        ["--config", str(config_path), "--chat-model", "gpt-4o-mini", "--show-config"],
        env={"ELROY_CHAT_MODEL": "env_model"},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "gpt-4o-mini" in result.stdout
    assert "env_model" not in result.stdout
    assert "config_file_model" not in result.stdout

    # Test 2: Environment variables override config file
    result = runner.invoke(
        app,
        ["--config", str(config_path), "--show-config"],
        env={"ELROY_CHAT_MODEL": "gpt-4o-mini"},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "gpt-4o-mini" in result.stdout
    assert "config_file_model" not in result.stdout

    # Test 3: Config file overrides defaults
    result = runner.invoke(
        app,
        ["--config", str(config_path), "--show-config"],
        env={},  # No environment variables
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "gpt-4o-mini" in result.stdout


def test_persona(user_token):

    runner = CliRunner(mix_stderr=True)
    config_path = str(Path(__file__).parent / "fixtures" / "test_config.yml")
    result = runner.invoke(
        app,
        [
            "--config",
            config_path,
            "--user-token",
            user_token,
            "--show-persona",
        ],
        env={},
        catch_exceptions=True,
    )

    assert result.exit_code == 0
    assert "jimbo" in result.stdout.lower()


def test_persona_assistant_specific_persona(elroy_context, user_token):
    set_system_persona(elroy_context, "You are a helpful assistant. Your name is Billy.")
    assert "Billy" in get_persona(elroy_context.session, elroy_context.config, elroy_context.user_id)
    reset_system_persona(elroy_context)
    assert "Elroy" in get_persona(elroy_context.session, elroy_context.config, elroy_context.user_id)


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
            "o1",
            "gpt4o_mini",
            "opus",
            "gpt4o",
            "o1_mini",
            "sonnet",
            "set_persona",
            "show_persona",
            "reset_persona",
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
