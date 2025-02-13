from pathlib import Path

from typer.testing import CliRunner

from elroy.cli.main import app
from elroy.config.ctx import ElroyContext
from elroy.repository.user.operations import reset_system_persona, set_persona
from elroy.repository.user.queries import get_persona


def test_persona(ctx: ElroyContext):

    runner = CliRunner(mix_stderr=True)
    config_path = str(Path(__file__).parent / "fixtures" / "test_config.yml")
    result = runner.invoke(
        app,
        [
            "--config",
            config_path,
            "--user-token",
            ctx.user_token,
            "--database-url",
            ctx.db.url,
            "show-persona",
        ],
        env={},
        catch_exceptions=True,
    )

    assert result.exit_code == 0
    assert "jimbo" in result.stdout.lower()


def test_persona_assistant_specific_persona(ctx: ElroyContext):
    set_persona(ctx, "You are a helpful assistant. Your name is Billy.")
    assert "Billy" in get_persona(ctx)
    reset_system_persona(ctx)
    assert "Elroy" in get_persona(ctx)
