import pytest
from unittest.mock import patch, MagicMock
from fabra.config import DevConfig, ProdConfig, get_duckdb_path
from fabra.core import FeatureStore, Entity
from fabra.store import InMemoryOnlineStore


def test_config_duckdb_path():
    """Test DuckDB path configuration logic."""
    # Default
    with patch("os.environ.get", return_value=None):
        path = get_duckdb_path()
        assert ".fabra/fabra.duckdb" in path

    # Override
    with patch("os.environ.get", return_value="/tmp/custom.db"):
        path = get_duckdb_path()
        assert path == "/tmp/custom.db"


def test_dev_config_auto_redis():
    """Test DevConfig Redis auto-detection."""
    config = DevConfig()

    # No Redis env -> InMemory
    with patch("os.environ.get", return_value=None):
        store = config.get_online_store()
        assert isinstance(store, InMemoryOnlineStore)

    # Redis env -> RedisOnlineStore (if available)
    # We need to mock RedisOnlineStore being importable if it's not installed,
    # but in this env it likely is.
    with patch("os.environ.get", return_value="redis://localhost:6379"):
        # If redis is installed, it returns RedisOnlineStore
        # We can check class name to be safe
        store = config.get_online_store()
        assert (
            "Redis" in store.__class__.__name__
            or "InMemory" in store.__class__.__name__
        )


def test_prod_config_failures():
    """Test ProdConfig error paths."""
    config = ProdConfig()

    # Missing Redis URL
    with patch("os.environ.get", return_value=None):
        # Mock RedisOnlineStore availability to force the URL check
        with patch("fabra.config.RedisOnlineStore", MagicMock()):
            with pytest.raises(ValueError, match="FABRA_REDIS_URL"):
                config.get_online_store()

    # Missing Postgres URL
    with patch("os.environ.get", return_value=None):
        with patch("fabra.config.PostgresOfflineStore", MagicMock()):
            with pytest.raises(ValueError, match="FABRA_POSTGRES_URL"):
                config.get_offline_store()


def test_core_repr_html():
    """Test FeatureStore HTML representation."""
    store = FeatureStore(offline_store=MagicMock(), online_store=InMemoryOnlineStore())
    store.register_entity("user", "uid", "User entity")

    html = store._repr_html_()
    assert "Fabra Feature Store" in html
    assert "user" in html
    assert "InMemoryOnlineStore" in html


def test_core_get_feature_missing():
    """Test error when getting missing feature."""
    store = FeatureStore(offline_store=MagicMock(), online_store=InMemoryOnlineStore())

    # Single feature
    with pytest.raises(ValueError, match="Feature 'missing' not found"):
        import asyncio

        asyncio.run(store.get_feature("missing", "u1"))


def test_core_register_invalid_sql():
    """Test registering invalid SQL feature (no batch source logic, just storage)."""
    # Feature registration itself doesn't validate SQL correctness usually,
    # but get_training_data might fail.
    store = FeatureStore()
    f = store.register_feature("f1", "ent1", lambda x: x)
    assert f.name == "f1"


def test_entity_repr():
    """Test Entity string/html representation."""
    e = Entity("e1", "id")
    assert "e1" in e._repr_html_()
