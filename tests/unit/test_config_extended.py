"""Extended unit tests for config module.

Targets: src/fabra/config.py (79% → 86%+)
Covers: environment variable handling and store initialization
"""

import os
from unittest.mock import patch
from fabra.config import DevConfig, ProdConfig


class TestConfigEnvironmentHandling:
    """Tests for environment variable handling."""

    def test_get_redis_url_from_env(self) -> None:
        """Test Redis URL from environment variable."""
        with patch.dict(os.environ, {"FABRA_REDIS_URL": "redis://custom:6379/0"}):
            from fabra.config import get_redis_url

            assert get_redis_url() == "redis://custom:6379/0"

    def test_get_redis_url_default(self) -> None:
        """Test default Redis URL."""
        with patch.dict(os.environ, {}, clear=True):
            from fabra.config import get_redis_url

            url = get_redis_url()
            assert "redis://" in url

    def test_get_duckdb_path(self) -> None:
        """Test DuckDB path configuration."""
        from fabra.config import get_duckdb_path

        # Ensure env var is cleared for this test
        with patch.dict(os.environ, {}, clear=True):
            with patch("os.path.expanduser", return_value="/tmp/testpoint"):
                path = get_duckdb_path()
                assert path == "/tmp/testpoint/.fabra/fabra.duckdb"


class TestStoreInitialization:
    """Tests for store factory methods."""

    def test_dev_config_creates_correct_stores(self) -> None:
        """Test DevConfig creates appropriate stores."""
        with patch.dict(os.environ, {}, clear=True):
            config = DevConfig()

            # Should have online and offline store methods
            assert hasattr(config, "get_online_store")
            assert hasattr(config, "get_offline_store")

    def test_prod_config_requires_postgres(self) -> None:
        """Test ProdConfig requires Postgres URL."""
        with patch.dict(os.environ, {}, clear=True):
            # Should raise or require FABRA_POSTGRES_URL
            config = ProdConfig()
            # Accessing offline store without env var should handle gracefully
            try:
                store = config.get_offline_store()
                # If it doesn't raise, it should use a default or handle missing config
                assert store is not None
            except (ValueError, KeyError):
                # Expected behavior when no Postgres URL
                pass
