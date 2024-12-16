from pathlib import Path

from typer.testing import CliRunner

from elroy.cli.main import app
from elroy.llm.persona import get_persona
from elroy.tools.user_preferences import reset_system_persona, set_system_persona


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


def test_persona_assistant_specific_persona(elroy_context):
    set_system_persona(elroy_context, "You are a helpful assistant. Your name is Billy.")
    assert "Billy" in get_persona(elroy_context.session, elroy_context.config, elroy_context.user_id)
    reset_system_persona(elroy_context)
    assert "Elroy" in get_persona(elroy_context.session, elroy_context.config, elroy_context.user_id)
