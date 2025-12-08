from typer.testing import CliRunner
from meridian.cli import app
from meridian.doctor import check_redis, check_postgres
from unittest.mock import patch

from pathlib import Path

runner = CliRunner()


def test_init_demo_scaffold(tmp_path: Path) -> None:
    """Test standard success path for init --demo."""
    # We chdir to tmp_path to avoid creating files in the project root
    with patch("os.getcwd", return_value=str(tmp_path)):
        # But init takes a path argument, so we can just pass absolute path?
        # The logic uses os.makedirs(name). If name is absolute it works.
        project_dir = tmp_path / "my_demo"

        result = runner.invoke(app, ["init", str(project_dir), "--demo"])

        assert result.exit_code == 0
        assert "Initialized demo project" in result.stdout

        # Check files
        assert (project_dir / "features.py").exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / ".gitignore").exists()

        # Check content
        content = (project_dir / "features.py").read_text()
        assert "@retriever" in content
        assert "chatbot_context" in content


def test_init_no_demo(tmp_path: Path) -> None:
    """Test init without demo flag."""
    project_dir = tmp_path / "empty_project"
    result = runner.invoke(app, ["init", str(project_dir)])

    assert result.exit_code == 0
    assert "Initialized empty project" in result.stdout
    assert (project_dir / "features.py").exists()
    content = (project_dir / "features.py").read_text()
    assert "store = FeatureStore()" in content
    assert "@retriever" not in content


def test_doctor_fix_suggestions() -> None:
    """Test that doctor checks return fix suggestions on failure."""

    # Test Redis failure with suggestion
    res = check_redis("redis://nonexistent:6379")
    # check_redis catches Exception and returns details
    assert res["status"] == "❌ Failed"
    assert "Fix: Try 'docker run" in res["details"]

    # Test Postgres failure (generic Exception caught)
    res = check_postgres("postgresql://bad:5432/db")
    assert res["status"] == "❌ Failed"
    # Postgres doesn't have a specific fix string added yet, just checks it doesn't crash
