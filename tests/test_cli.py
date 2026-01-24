from pathlib import Path
from tempfile import TemporaryDirectory

from typer.testing import CliRunner

from elroy.cli.main import app
from elroy.core.ctx import ElroyContext
from elroy.repository.user.operations import reset_system_persona, set_persona
from elroy.repository.user.queries import get_persona


def test_persona(ctx: ElroyContext):

    runner = CliRunner()
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


def test_install_skills():
    """Test that claude skills can be installed to a custom directory."""
    runner = CliRunner()

    with TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"

        result = runner.invoke(
            app,
            ["install-skills", "--skills-dir", str(skills_dir)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Command failed: {result.stdout}"
        assert "successfully" in result.stdout.lower()

        # Check that skills were installed
        expected_skills = ["remember", "recall", "list-memories", "remind", "list-reminders", "ingest"]
        for skill in expected_skills:
            skill_path = skills_dir / skill
            assert skill_path.exists(), f"Skill {skill} was not installed"
            assert (skill_path / "SKILL.md").exists(), f"SKILL.md not found for {skill}"


def test_uninstall_skills():
    """Test that claude skills can be uninstalled from a custom directory."""
    runner = CliRunner()

    with TemporaryDirectory() as tmpdir:
        skills_dir = Path(tmpdir) / "skills"

        # First install
        result = runner.invoke(
            app,
            ["install-skills", "--skills-dir", str(skills_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        # Verify skills are installed
        assert (skills_dir / "remember").exists()

        # Now uninstall
        result = runner.invoke(
            app,
            ["install-skills", "--uninstall", "--skills-dir", str(skills_dir)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert "uninstalled successfully" in result.stdout.lower()

        # Check that skills were removed
        expected_skills = ["remember", "recall", "list-memories", "remind", "list-reminders", "ingest"]
        for skill in expected_skills:
            skill_path = skills_dir / skill
            assert not skill_path.exists(), f"Skill {skill} was not uninstalled"
