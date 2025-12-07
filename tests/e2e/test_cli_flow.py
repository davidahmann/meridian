from typer.testing import CliRunner
from meridian.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Meridian OSS v" in result.stdout


def test_doctor_config_check() -> None:
    """
    Test that 'doctor' runs.
    It might fail or pass depending on the env, but we check it runs
    and outputs something intelligible.
    """
    result = runner.invoke(app, ["doctor"])
    # It might exit with 1 if checks fail (e.g. no redis), so we don't assert 0 blindly
    # unless we mock everything. For now, let's just ensure it calls the command.
    assert "Meridian Doctor" in result.stdout
