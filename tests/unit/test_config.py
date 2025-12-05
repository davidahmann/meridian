import os
import pytest
from unittest.mock import patch
from meridian.config import get_config, DevConfig, ProdConfig, get_store_factory
from meridian.store.offline import DuckDBOfflineStore
from meridian.store.online import InMemoryOnlineStore

# Mock Postgres/Redis imports if they are not installed in the test env
# But for unit tests we can mock the classes themselves or the config module behavior.
# However, since we are testing the config module which imports them, we rely on them being importable or None.
# In the dev environment, they might be None if dependencies are missing.
# But we installed 'asyncpg' and 'redis' in previous steps, so they should be available.


def test_default_config() -> None:
    """Test that default config is DevConfig."""
    with patch.dict(os.environ, {}, clear=True):
        config = get_config()
        assert isinstance(config, DevConfig)

        offline, online = get_store_factory()
        assert isinstance(offline, DuckDBOfflineStore)
        assert isinstance(online, InMemoryOnlineStore)


def test_dev_config_explicit() -> None:
    """Test explicit development environment."""
    with patch.dict(os.environ, {"MERIDIAN_ENV": "development"}, clear=True):
        config = get_config()
        assert isinstance(config, DevConfig)


def test_prod_config_missing_vars() -> None:
    """Test production config raises error if vars missing."""
    with patch.dict(os.environ, {"MERIDIAN_ENV": "production"}, clear=True):
        config = get_config()
        assert isinstance(config, ProdConfig)

        # Should raise ValueError because MERIDIAN_POSTGRES_URL is missing
        with pytest.raises(ValueError, match="MERIDIAN_POSTGRES_URL"):
            config.get_offline_store()

        # Mock offline store success to test online store failure
        with patch.object(ProdConfig, "get_offline_store"):
            with pytest.raises(ValueError, match="MERIDIAN_REDIS_URL"):
                config.get_online_store()


def test_prod_config_success() -> None:
    """Test production config with valid vars."""
    env_vars = {
        "MERIDIAN_ENV": "production",
        "MERIDIAN_POSTGRES_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        "MERIDIAN_REDIS_URL": "redis://localhost:6379/0",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        config = get_config()
        assert isinstance(config, ProdConfig)

        # We need to ensure PostgresOfflineStore and RedisOnlineStore are importable
        # If they are not (e.g. missing deps), this test might fail with ImportError or NameError
        # But we assume deps are installed.

        try:
            from meridian.store.postgres import PostgresOfflineStore
            from meridian.store.redis import RedisOnlineStore

            offline = config.get_offline_store()
            assert isinstance(offline, PostgresOfflineStore)
            # SQLAlchemy masks password in string representation
            assert offline.engine.url.drivername == "postgresql+asyncpg"
            assert offline.engine.url.host == "localhost"
            assert offline.engine.url.database == "db"

            online = config.get_online_store()
            assert isinstance(online, RedisOnlineStore)

        except ImportError:
            pytest.skip("Production dependencies not installed")
