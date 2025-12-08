from unittest.mock import MagicMock, patch
from meridian.doctor import check_redis, check_postgres, run_doctor


def test_check_redis_skipped() -> None:
    res = check_redis(None)
    assert res["status"] == "⏭️ Skipped"


def test_check_redis_connected() -> None:
    with patch("redis.from_url") as mock_redis:
        mock_redis.return_value.ping.return_value = True
        res = check_redis("redis://localhost")
        assert res["status"] == "✅ Connected"


def test_check_postgres_skipped() -> None:
    res = check_postgres(None)
    assert res["status"] == "⏭️ Skipped"


def test_check_postgres_connected() -> None:
    with patch("sqlalchemy.create_engine") as mock_engine:
        mock_conn = MagicMock()
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
        res = check_postgres("postgresql://localhost")
        assert res["status"] == "✅ Connected"


def test_run_doctor_print() -> None:
    # Verify it runs without error (smoke test)
    # We patch print/console
    with patch("meridian.doctor.console") as mock_console:
        # Need to mock env vars check logic?
        run_doctor()
        # Should print stuff
        assert mock_console.print.called
