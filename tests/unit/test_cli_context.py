from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from meridian.cli import app

runner = CliRunner()


def test_context_command_success() -> None:
    """Test standard success path with mocked urllib."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"context_id": "123", "items": []}'
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        result = runner.invoke(app, ["context", "explain", "ctx_123"])

        assert result.exit_code == 0
        assert "Fetching trace for ctx_123" in result.stdout
        assert "Context Trace: ctx_123" in result.stdout

        # Verify URL construction
        args, _ = mock_urlopen.call_args
        req = args[0]
        assert req.full_url == "http://127.0.0.1:8000/context/ctx_123/explain"


def test_context_command_server_error() -> None:
    """Test server 500/404 handling."""
    mock_response = MagicMock()
    mock_response.status = 404
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = runner.invoke(app, ["context", "explain", "ctx_404"])
        assert result.exit_code == 1
        assert "Server returned 404" in result.stdout


def test_context_command_connection_error() -> None:
    """Test connection refused."""
    import urllib.error

    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("Connection refused"),
    ):
        result = runner.invoke(app, ["context", "explain", "ctx_dead"])
        assert result.exit_code == 1
        assert "Connection Failed" in result.stdout
