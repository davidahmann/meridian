from unittest.mock import patch
from typer.testing import CliRunner
from meridian.cli import app

runner = CliRunner()


def test_version() -> None:
    with patch("importlib.metadata.version", return_value="1.2.3"):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Meridian OSS v1.2.3" in result.stdout


def test_doctor_cmd() -> None:
    with patch("meridian.doctor.run_doctor") as mock_run:
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        mock_run.assert_called()


def test_worker_cmd() -> None:
    # Test failure path (file not found)
    with patch("os.path.exists", return_value=False):
        result = runner.invoke(app, ["worker", "missing.py"])
        assert result.exit_code != 0
