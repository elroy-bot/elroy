from pathlib import Path

from typer.testing import CliRunner

from elroy.cli.main import app


def test_config_precedence():
    """Test that config values are properly prioritized:
    CLI args > env vars > config file > defaults
    """
    runner = CliRunner()
    config_path = Path(__file__).parent / "fixtures" / "test_config.yml"

    # Test 1: CLI args override everything
    result = runner.invoke(
        app,
        ["--config", str(config_path), "--chat-model", "cli_model", "show-config"],
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
        ["--config", str(config_path), "show-config"],
        env={"ELROY_CHAT_MODEL": "env_model"},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "env_model" in result.stdout
    assert "config_file_model" not in result.stdout

    # Test 3: Config file overrides defaults
    result = runner.invoke(
        app,
        ["--config", str(config_path), "show-config"],
        env={},  # No environment variables
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "config_file_model" in result.stdout
